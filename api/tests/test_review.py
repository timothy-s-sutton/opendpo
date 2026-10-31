"""Review and approval (workstream 9): the walkthrough's approval path as three people,
segregation of duties, the § 7152(a)(9) authority check, return and resubmit, the DPO's
risk acceptance and the routing plan."""
from datetime import date, timedelta

import psycopg
import pytest

from opendpo import approval
from opendpo.config import settings
from opendpo.db import tenant_tx

from .conftest import HARBOR, as_user
from .test_agent import fixture_provider, harms_signed, opened  # noqa: F401  (fixtures)
from .test_assessment import rules_loaded  # noqa: F401

BASE = f"/api/tenants/{HARBOR}"


@pytest.fixture
def drafted(client, opened, fixture_provider):  # noqa: F811
    r = client.post(f"{BASE}/assessments/{opened}/draft", json={}, headers=as_user("ana.patel"))
    assert r.status_code == 200, r.text
    return opened


def get(client, aid, who="ana.patel"):
    return client.get(f"{BASE}/assessments/{aid}", headers=as_user(who)).json()


def section(a, sid):
    return next(s for s in a["sections"] if s["id"] == sid)


def decide_to_go_ahead(client, aid, who="ana.patel"):
    dec = section(get(client, aid), "decision")
    body = {"initiate": "yes", "rationale": "Go ahead once the safeguards are in place."}
    r = client.put(f"{BASE}/assessments/{aid}/sections/decision", json={"body": body, "base_revision": dec["revision"]},
                   headers=as_user(who))
    assert r.status_code == 200, r.text


def act(client, aid, who, decision="approve", **kw):
    return client.post(f"{BASE}/assessments/{aid}/review", json={"decision": decision, **kw}, headers=as_user(who))


def test_submit_needs_a_decision(client, drafted):
    r = client.post(f"{BASE}/assessments/{drafted}/submit", json={}, headers=as_user("ana.patel"))
    assert r.status_code == 422 and any("section 7" in p for p in r.json()["detail"]["problems"])


def test_the_walkthrough_approval_path(client, drafted):
    decide_to_go_ahead(client, drafted)
    r = client.post(f"{BASE}/assessments/{drafted}/submit", json={}, headers=as_user("ana.patel"))
    assert r.status_code == 200, r.text
    assert r.json()["routing_level"] == "high"
    assert r.json()["plan"]["final"] == ["dpo", "privacy_counsel"] and "POS-RA-004" in r.json()["plan"]["source"]
    # Editing stops while it is in review.
    purpose = section(get(client, drafted), "purpose")
    assert client.put(f"{BASE}/assessments/{drafted}/sections/purpose", json={
        "body": {"text": "Changed during review"}, "base_revision": purpose["revision"]},
        headers=as_user("ana.patel")).status_code == 409
    # SOD-1: the analyst who asked for the draft and submitted it cannot approve it.
    r = act(client, drafted, "ana.patel")
    assert r.status_code == 403 and r.json()["detail"]["reasons"][0].startswith("SOD-1")
    # Final approvers wait for the provisional approval.
    r = act(client, drafted, "carla.mendes")
    assert r.status_code == 403 and "privacy_analyst" in r.json()["detail"]["reasons"][0]
    assert get(client, drafted, "ben.okafor")["review"]["can_act"] is True
    assert act(client, drafted, "ben.okafor").json() == {"status": "in_review", "step": "provisional",
                                                         "role": "privacy_analyst"}
    # SOD-2: one approval per person per round.
    r = act(client, drafted, "ben.okafor")
    assert r.status_code == 403 and r.json()["detail"]["reasons"][0].startswith("SOD-2")
    assert act(client, drafted, "devon.hart", has_initiation_authority=True).json()["status"] == "in_review"
    r = act(client, drafted, "carla.mendes", note="Notices must be live ten business days before use.")
    assert r.json() == {"status": "approved", "step": "final", "role": "privacy_counsel"}
    a = get(client, drafted, "avery.shaw")
    assert a["status"] == "approved"
    assert a["review"]["next_review_due"] == (date.today().replace(year=date.today().year + 1)).isoformat()
    sec9 = section(a, "approval")["body"]
    assert [x["name"] for x in sec9["reviewers"]] == ["Ben Okafor", "Devon Hart", "Carla Mendes"]
    assert sec9["reviewers"][1]["has_initiation_authority"] and sec9["reviewers"][2]["legal_counsel"]
    with tenant_tx(HARBOR) as conn:
        actions = [e["action"] for e in conn.execute(
            "SELECT action FROM audit_event WHERE object_id = %s ORDER BY seq", (drafted,)).fetchall()]
    assert actions[-5:] == ["assessment.submitted", "assessment.review_approve", "assessment.review_approve",
                            "assessment.review_approve", "assessment.approved"]
    with tenant_tx(HARBOR) as conn:
        denied = conn.execute("""SELECT count(*) AS n FROM audit_event WHERE action = 'access.denied'
                                 AND payload->>'attempted' = 'assessment.approve'""").fetchone()["n"]
    assert denied >= 2


def test_someone_must_have_authority_over_going_ahead(client, drafted):
    decide_to_go_ahead(client, drafted)
    client.post(f"{BASE}/assessments/{drafted}/submit", json={}, headers=as_user("ana.patel"))
    act(client, drafted, "ben.okafor")
    act(client, drafted, "devon.hart")
    r = act(client, drafted, "carla.mendes")
    assert r.status_code == 422 and "7152(a)(9)" in r.json()["detail"]["problems"][0]
    assert act(client, drafted, "carla.mendes", has_initiation_authority=True).json()["status"] == "approved"


def test_return_and_resubmit(client, drafted):
    decide_to_go_ahead(client, drafted)
    client.post(f"{BASE}/assessments/{drafted}/submit", json={}, headers=as_user("ana.patel"))
    assert act(client, drafted, "ben.okafor", "return").status_code == 422          # a note is required
    assert act(client, drafted, "ben.okafor", "return",
               note="Add who will run the bias audit.").json()["status"] == "returned"
    sg = section(get(client, drafted), "safeguards")
    sg["body"]["safeguards"][0]["owner"] = "Head of Talent Acquisition, with an outside auditor"
    assert client.put(f"{BASE}/assessments/{drafted}/sections/safeguards", json={
        "body": sg["body"], "base_revision": sg["revision"]}, headers=as_user("ana.patel")).status_code == 200
    r = client.post(f"{BASE}/assessments/{drafted}/submit", json={}, headers=as_user("ana.patel"))
    assert r.json()["round"] == 2
    a = get(client, drafted)
    assert a["review"]["next"] == {"step": "provisional", "roles": ["privacy_analyst"], "done": False}
    assert [d["decision"] for d in a["review"]["decisions"]] == ["return"]


def test_reject_is_final(client, drafted):
    decide_to_go_ahead(client, drafted)
    client.post(f"{BASE}/assessments/{drafted}/submit", json={}, headers=as_user("ana.patel"))
    assert act(client, drafted, "devon.hart", "reject", note="Do not use this vendor.").json()["status"] == "rejected"
    assert client.post(f"{BASE}/assessments/{drafted}/submit", json={}, headers=as_user("ana.patel")).status_code == 409


def test_dpo_accepts_a_high_residual_risk(client, drafted):
    risks = section(get(client, drafted), "risks")
    body = risks["body"]
    body["risks"][0].update(residual_likelihood="high", residual_severity="high")
    assert client.put(f"{BASE}/assessments/{drafted}/sections/risks", json={"body": body, "base_revision": 1},
                      headers=as_user("ana.patel")).status_code == 200
    # Going ahead is blocked until the DPO accepts the risk (WF-20).
    dec = {"initiate": "yes", "rationale": "Go ahead."}
    r = client.put(f"{BASE}/assessments/{drafted}/sections/decision", json={"body": dec, "base_revision": 1},
                   headers=as_user("ana.patel"))
    assert r.status_code == 422 and "risk acceptance" in r.json()["detail"]["problems"][0]
    acc = {"risk": "r1", "reason": "The bias audit is booked for December and go-live waits for its result.",
           "review_date": (date.today() + timedelta(days=90)).isoformat()}
    assert client.post(f"{BASE}/assessments/{drafted}/risk-acceptances", json=acc,
                       headers=as_user("carla.mendes")).status_code == 403
    r = client.post(f"{BASE}/assessments/{drafted}/risk-acceptances", json=acc, headers=as_user("devon.hart"))
    assert r.status_code == 200 and r.json()["residual"] == "high" and r.json()["by_name"] == "Devon Hart"
    assert client.post(f"{BASE}/assessments/{drafted}/risk-acceptances", json=acc,
                       headers=as_user("devon.hart")).status_code == 409
    assert client.post(f"{BASE}/assessments/{drafted}/risk-acceptances", json={**acc, "risk": "r2"},
                       headers=as_user("devon.hart")).status_code == 422     # r2 is low; nothing to accept
    assert client.put(f"{BASE}/assessments/{drafted}/sections/decision", json={"body": dec, "base_revision": 1},
                      headers=as_user("ana.patel")).status_code == 200
    assert get(client, drafted)["computed"]["proceed_blockers"] == []


def test_approvals_cannot_be_changed(client, drafted):
    decide_to_go_ahead(client, drafted)
    client.post(f"{BASE}/assessments/{drafted}/submit", json={}, headers=as_user("ana.patel"))
    act(client, drafted, "ben.okafor")
    with psycopg.connect(settings.owner_dsn) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE assessment_approval SET decision = 'reject' WHERE assessment_id = %s", (drafted,))


def test_routing_plans():
    std = approval.plan("high", "standard", {})
    assert (std.provisional, std.final, std.each_final_role) == (["privacy_analyst"], ["dpo", "privacy_counsel"], True)
    lean = approval.plan("high", "lean", {})
    assert lean.provisional == [] and not lean.each_final_role
    assert approval.progress(lean, [{"decision": "approve", "step": "final", "role": "dpo"}])["done"]
    low = approval.plan("low", "standard", {})
    assert approval.progress(low, [])["roles"] == ["privacy_analyst"]
    custom = {"POS-RA-004": {"parameters": {"routing": {"medium": {"provisional": [], "final": ["dpo"]}}}}}
    assert approval.plan("medium", "standard", custom).final == ["dpo"]
    assert approval.next_review(date(2028, 2, 29), "high", {}) == date(2029, 2, 28)
    assert approval.next_review(date(2026, 11, 1), "moderate", {}) == date(2028, 11, 1)
