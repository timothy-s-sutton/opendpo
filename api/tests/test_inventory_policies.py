"""Inventory and policies (workstream 7): the Harbor seed, read access, the policy templates
and their review gate, and assessments recording what they were made with."""
import psycopg
import pytest

from opendpo import policies
from opendpo.config import settings
from opendpo.db import tenant_tx

from .conftest import HARBOR, as_user

BASE = f"/api/tenants/{HARBOR}"


def test_templates_load_and_positions_point_at_sections():
    sts = {s.template.id: s for s in policies.load()}
    assert set(sts) == {"ai-governance", "risk-assessment"}
    types = {p.type for s in sts.values() for p in s.template.positions}
    assert types == {"requirement", "prohibition", "threshold", "approval_rule", "default", "conditional_permission"}


def test_templates_wait_on_review():
    for s in policies.load():
        if s.reviewed:
            continue
        assert s.problems == ["not yet reviewed"] or "review it again" in s.problems[0]


def test_seed_matches_the_templates():
    """The committed seed must be rebuilt whenever a template or the inventory changes."""
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("build_seed_004", root / "scripts" / "seed" / "build_seed_004.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    committed = (root / "api" / "migrations" / "seed_demo_004.sql").read_text(encoding="utf-8")
    assert mod.main() == committed, "run: python3 scripts/seed/build_seed_004.py > api/migrations/seed_demo_004.sql"


def test_harbor_activity_has_its_inventory(client):
    acts = client.get(f"{BASE}/inventory/activities", headers=as_user("ana.patel")).json()
    assert [a["name"] for a in acts] == ["AI resume screening for warehouse and driver roles"]
    a = client.get(f"{BASE}/inventory/activities/{acts[0]['id']}", headers=as_user("ana.patel")).json()
    assert a["human_review"] == "limited" and a["ai_role"] == "materially_influences"
    assert [c["name"] for c in a["ai_components"]] == ["Brightpath Match Score"]
    assert {r["name"] for r in a["recipients"]} == {"Brightpath Hiring", "Crestline Software"}
    assert len(a["data_categories"]) == 5 and a["people_affected"]["job_applicants"]["US-CA"] == 21000


def test_submitter_cannot_read_inventory(client):
    assert client.get(f"{BASE}/inventory/activities", headers=as_user("sam.rivera")).status_code == 403


def test_policies_show_positions_and_review_status(client):
    body = client.get(f"{BASE}/policies", headers=as_user("sam.rivera")).json()
    titles = [p["title"] for p in body["policies"]]
    assert titles == ["AI governance and acceptable AI use", "Privacy and AI risk assessment"]
    ai = body["policies"][0]
    assert ai["confirmed_by_name"] == "Devon Hart" and ai["proposed_by_name"] == "Carla Mendes"
    assert any(p["position_key"] == "POS-AI-002" for p in ai["positions"])
    assert "Harbor Staffing" in ai["sections"][0]["text"] and "{organization}" not in str(ai["sections"])
    assert set(ai["template_review"]) == {"version", "reviewed", "problems"}


def test_policy_versions_are_fixed():
    with psycopg.connect(settings.owner_dsn) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE policy_position SET statement = 'x'")
    with psycopg.connect(settings.owner_dsn) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE policy_version SET sections = '[]'")


def test_proposer_cannot_confirm_own_policy():
    with psycopg.connect(settings.owner_dsn) as conn:
        pol = conn.execute("SELECT id, tenant_id FROM policy LIMIT 1").fetchone()
        uid = conn.execute("SELECT id FROM app_user WHERE username = 'devon.hart'").fetchone()[0]
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("""INSERT INTO policy_version (id, tenant_id, policy_id, version, sections, status,
                                                        proposed_by, confirmed_by, confirmed_at)
                            VALUES (gen_random_uuid(), %s, %s, 99, '[]', 'confirmed', %s, %s, now())""",
                         (pol[1], pol[0], uid, uid))


def test_inventory_is_tenant_isolated():
    from opendpo.db import global_tx
    with global_tx() as conn:
        assert conn.execute("SELECT count(*) AS n FROM processing_activity").fetchone()["n"] == 0
    with tenant_tx(HARBOR) as conn:
        assert conn.execute("SELECT count(*) AS n FROM processing_activity").fetchone()["n"] == 1


def test_job_titles_are_seeded():
    with tenant_tx(HARBOR) as conn:
        row = conn.execute("SELECT job_title FROM app_user WHERE username = 'devon.hart'").fetchone()
    assert row["job_title"].startswith("Data Protection Officer")
