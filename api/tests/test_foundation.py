import uuid

import psycopg
import pytest
from psycopg.rows import dict_row

from opendpo import audit
from opendpo.config import settings
from opendpo.db import tenant_tx

from .conftest import HARBOR, as_user, token_for, user_id


def test_health(client):
    body = client.get("/api/health").json()
    assert body["database"] and body["policy_engine"]


def test_no_token_is_rejected(client):
    assert client.get("/api/me").status_code == 401


def test_wrong_audience_is_rejected(client):
    bad = token_for("ana.patel", aud="some-other-app")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_me_lists_memberships(client):
    body = client.get("/api/me", headers=as_user("ana.patel")).json()
    assert body["display_name"] == "Ana Patel"
    assert body["tenants"][0]["name"] == "Harbor Staffing"
    assert body["tenants"][0]["roles"] == ["privacy_analyst"]


# PLT-01: tenant isolation is enforced by the database, not just the API.
def test_rls_hides_rows_without_a_tenant():
    with psycopg.connect(settings.app_dsn, row_factory=dict_row) as conn:
        assert conn.execute("SELECT count(*) AS n FROM membership").fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM tenant").fetchone()["n"] == 0


def test_rls_isolates_tenants(superuser):
    other_ws, other = uuid.uuid4(), uuid.uuid4()
    superuser.execute("INSERT INTO workspace (id, name) VALUES (%s, 'Other firm')", (other_ws,))
    superuser.execute("INSERT INTO tenant (id, workspace_id, name) VALUES (%s, %s, 'Other client')",
                      (other, other_ws))
    superuser.execute("INSERT INTO membership (tenant_id, user_id, role) VALUES (%s, %s, 'dpo')",
                      (other, user_id("sam.rivera")))
    try:
        _check_isolation(other)
    finally:
        superuser.execute("DELETE FROM membership WHERE tenant_id = %s", (other,))
        superuser.execute("DELETE FROM tenant WHERE id = %s", (other,))
        superuser.execute("DELETE FROM workspace WHERE id = %s", (other_ws,))


def _check_isolation(other):
    with tenant_tx(HARBOR) as conn:
        names = {r["name"] for r in conn.execute("SELECT name FROM tenant")}
        assert names == {"Harbor Staffing"}
        n = conn.execute("SELECT count(*) AS n FROM membership WHERE tenant_id = %s", (other,)).fetchone()["n"]
        assert n == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO membership (tenant_id, user_id, role) VALUES (%s, %s, 'dpo')",
                         (other, user_id("ana.patel")))


def test_other_tenant_is_not_found(client):
    r = client.get(f"/api/tenants/{uuid.uuid4()}", headers=as_user("ana.patel"))
    assert r.status_code == 404


def test_submitter_cannot_read_audit(client):
    r = client.get(f"/api/tenants/{HARBOR}/audit", headers=as_user("sam.rivera"))
    assert r.status_code == 403


def test_allowed_actions_reflect_role(client):
    body = client.get(f"/api/tenants/{HARBOR}", headers=as_user("avery.shaw")).json()
    assert "audit.export" in body["allowed_actions"]
    assert "assessment.approve" not in body["allowed_actions"]


def test_denied_attempt_is_audited(client):
    r = client.post(f"/api/tenants/{HARBOR}/intended-use/ack", headers=as_user("sam.rivera"))
    assert r.status_code == 403
    events = client.get(f"/api/tenants/{HARBOR}/audit", headers=as_user("avery.shaw")).json()
    assert any(e["action"] == "access.denied" and e["payload"]["attempted"] == "tenant.ack_intended_use"
               for e in events)


def test_intended_use_ack_is_audited(client):
    r = client.post(f"/api/tenants/{HARBOR}/intended-use/ack", headers=as_user("terry.lin"))
    assert r.status_code == 200
    events = client.get(f"/api/tenants/{HARBOR}/audit", headers=as_user("avery.shaw")).json()
    assert any(e["action"] == "tenant.intended_use_acknowledged" for e in events)


def test_export_verifies_chain(client):
    body = client.get(f"/api/tenants/{HARBOR}/audit/export", headers=as_user("avery.shaw")).json()
    assert body["verification"]["ok"] is True
    seqs = [e["seq"] for e in body["events"]]
    assert seqs == list(range(1, len(seqs) + 1))


# SOD-5: the log is append-only, even for its owner.
def test_audit_rows_cannot_be_updated():
    with psycopg.connect(settings.owner_dsn) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE audit_event SET action = 'x'")


def test_app_role_cannot_delete_audit():
    with tenant_tx(HARBOR) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM audit_event")


# PLT-41: tampering by someone who bypasses the database controls is detected.
def test_tampering_is_detected(client, superuser):
    with tenant_tx(HARBOR) as conn:
        audit.append(conn, HARBOR, audit.Actor("system", "test"), "test.event", payload={"n": 1})
        audit.append(conn, HARBOR, audit.Actor("system", "test"), "test.event", payload={"n": 2})
        target = conn.execute("SELECT max(seq) - 1 AS s FROM audit_event").fetchone()["s"]
    superuser.execute("ALTER TABLE audit_event DISABLE TRIGGER audit_event_no_update")
    try:
        superuser.execute("UPDATE audit_event SET payload = '{\"n\": 99}' WHERE tenant_id = %s AND seq = %s",
                          (HARBOR, target))
        with tenant_tx(HARBOR) as conn:
            result = audit.verify(conn, HARBOR)
        assert not result.ok and result.first_broken_seq == target
        assert result.problem == "event content changed after it was written"
    finally:
        superuser.execute("UPDATE audit_event SET payload = '{\"n\": 1}' WHERE tenant_id = %s AND seq = %s",
                          (HARBOR, target))
        superuser.execute("ALTER TABLE audit_event ENABLE TRIGGER audit_event_no_update")
    with tenant_tx(HARBOR) as conn:
        assert audit.verify(conn, HARBOR).ok
