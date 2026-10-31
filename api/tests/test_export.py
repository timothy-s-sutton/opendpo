"""Exports (WF-16, WF-21, USE-03): one approved assessment, two outputs."""
import pytest

from opendpo.db import tenant_tx

from .conftest import HARBOR, as_user
from .test_agent import fixture_provider, harms_signed, opened  # noqa: F401
from .test_assessment import rules_loaded  # noqa: F401
from .test_review import act, decide_to_go_ahead, drafted  # noqa: F401

BASE = f"/api/tenants/{HARBOR}"


@pytest.fixture
def approved(client, drafted):  # noqa: F811
    decide_to_go_ahead(client, drafted)
    client.post(f"{BASE}/assessments/{drafted}/submit", json={}, headers=as_user("ana.patel"))
    act(client, drafted, "ben.okafor")
    act(client, drafted, "devon.hart", has_initiation_authority=True)
    assert act(client, drafted, "carla.mendes").json()["status"] == "approved"
    return drafted


def export(client, aid, kind, fmt="json", who="avery.shaw"):
    return client.get(f"{BASE}/assessments/{aid}/export?kind={kind}&fmt={fmt}", headers=as_user(who))


def test_internal_has_everything(client, approved):
    r = export(client, approved, "internal").json()
    ids = [s["id"] for s in r["sections"]]
    assert ids == ["purpose", "personal_information", "operations", "benefits", "risks", "safeguards", "decision",
                   "contributors", "approval", "obligations", "policy_check"]
    risks = next(s for s in r["sections"] if s["id"] == "risks")["body"]["risks"]
    assert risks[0]["inherent"] == "high" and risks[0]["residual"] == "moderate"
    assert r["made_with"]["routing"]["level"] == "high" and r["triage"] and r["history"]
    assert r["ai_draft_label"].startswith("AI-generated draft") and "proof of concept" in r["notice"]


def test_regulator_report_leaves_out_what_the_rules_do_not_require(client, approved):
    r = export(client, approved, "regulator").json()
    ids = [s["id"] for s in r["sections"]]
    assert ids == ["purpose", "personal_information", "operations", "safeguards", "decision", "contributors",
                   "approval"]
    sg = next(s for s in r["sections"] if s["id"] == "safeguards")["body"]["safeguards"]
    assert all("addresses" not in g for g in sg)
    approval = next(s for s in r["sections"] if s["id"] == "approval")["body"]
    assert [x["name"] for x in approval["reviewers"]] == ["Ben Okafor", "Devon Hart"]
    assert approval["counsel_omitted"] is True
    assert "§ 7157" in r["pending_verification"] and "made_with" not in r


def test_html_prints_and_escapes(client, approved):
    page = export(client, approved, "regulator", fmt="html").text
    assert page.startswith("<!doctype html>") and "Risk assessment report" in page
    assert "Legal counsel who gave legal advice is not named" in page
    assert "<script" not in page.lower()
    internal = export(client, approved, "internal", fmt="html").text
    assert "Appendices" in internal and "Edit history" in internal and "Draft." not in internal


def test_regulator_report_needs_approval(client, drafted):  # noqa: F811
    assert export(client, drafted, "regulator").status_code == 409
    page = export(client, drafted, "internal", fmt="html").text
    assert "<strong>Draft.</strong>" in page


def test_who_can_export_and_it_is_logged(client, approved):
    assert export(client, approved, "internal", who="sam.rivera").status_code == 403
    export(client, approved, "regulator")
    with tenant_tx(HARBOR) as conn:
        e = conn.execute("""SELECT payload FROM audit_event WHERE object_id = %s AND action = 'assessment.exported'
                            ORDER BY seq DESC LIMIT 1""", (approved,)).fetchone()
    assert e["payload"]["kind"] == "regulator"


def test_returned_rounds_read_properly(client, drafted):  # noqa: F811
    decide_to_go_ahead(client, drafted)
    client.post(f"{BASE}/assessments/{drafted}/submit", json={}, headers=as_user("ana.patel"))
    act(client, drafted, "ben.okafor", "return", note="Name the auditor.")
    page = export(client, drafted, "internal", fmt="html").text
    assert "Ben Okafor (privacy analyst) returned it on" in page
    assert "Revision 1 of 10 sections: OpenDPO agent, for Ana Patel" in page
