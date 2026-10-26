"""Intake and triage through the API: submission, triage with citations, the "not sure"
path (WF-08) and analyst confirmation (WF-06). Needs the database and OPA, like
test_foundation.py."""
import copy

import psycopg
import pytest
from psycopg.rows import dict_row

from opendpo import main
from opendpo.config import settings

from .conftest import HARBOR, as_user
from .test_triage import FIXTURE

BASE = f"/api/tenants/{HARBOR}"


@pytest.fixture(autouse=True)
def rules_loaded():
    main.publish_content_to_policy_engine(retries=3)


def new_project(client, answers=None, who="sam.rivera"):
    r = client.post(f"{BASE}/projects", json={"answers": answers or FIXTURE["answers"]}, headers=as_user(who))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_form_is_json_schema_with_definitions(client):
    body = client.get(f"{BASE}/intake/form", headers=as_user("sam.rivera")).json()
    schema = body["schema"]
    assert schema["$schema"].endswith("2020-12/schema")
    role = schema["properties"]["ai.role"]
    assert role["x-opendpo"]["definitions"][0]["citation"] == "Cal. Code Regs. tit. 11, § 7001(e)"
    assert body["scoping"]["scope.ccpa_applies"] is True


def test_submit_runs_triage_with_citations(client):
    pid = new_project(client)
    r = client.post(f"{BASE}/projects/{pid}/submit", headers=as_user("sam.rivera"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "triaged" and body["version"] == 1
    result = body["result"]
    assert [a["assessment"] for a in result["assessments"]] == ["ccpa_risk_assessment"]
    admt = next(c for c in result["classifications"] if c["rule"] == "CCPA-CLASS-ADMT")
    assert any(c["id"] == "ccpa-7001-e-1" for c in admt["citations"])
    # Rules not yet verified are listed, not run.
    assert any(n["rule"] == "CO-DEPLOYER-NOTICE" for n in result["not_run"])
    detail = client.get(f"{BASE}/projects/{pid}", headers=as_user("ana.patel")).json()
    assert detail["status"] == "triaged" and detail["triage"]["status"] == "proposed"


def test_incomplete_intake_is_refused(client):
    answers = copy.deepcopy(FIXTURE["answers"])
    del answers["ai.role"]
    pid = new_project(client, answers)
    r = client.post(f"{BASE}/projects/{pid}/submit", headers=as_user("sam.rivera"))
    assert r.status_code == 422
    assert {"question": "ai.role", "problem": "needs an answer"} in r.json()["detail"]["problems"]


def test_not_sure_waits_for_an_analyst(client):
    answers = {k: v for k, v in FIXTURE["answers"].items() if k.startswith("project.") or k == "subjects"}
    answers.update({"project.uses_ai": "not_sure", "project.locations": ["US-other"]})
    pid = new_project(client, answers)
    assert client.post(f"{BASE}/projects/{pid}/submit", headers=as_user("sam.rivera")).json()["status"] \
        == "awaiting_clarification"
    # Submitters cannot ask for the clarification; analysts can.
    q = {"question": "Does the vendor's matching score come from a trained model?"}
    assert client.post(f"{BASE}/projects/{pid}/clarification", json=q, headers=as_user("sam.rivera")).status_code == 403
    assert client.post(f"{BASE}/projects/{pid}/clarification", json=q, headers=as_user("ana.patel")).status_code == 200
    # The submitter settles it and resubmits; triage runs.
    answers["project.uses_ai"] = "no"
    client.put(f"{BASE}/projects/{pid}/answers", json={"answers": answers}, headers=as_user("sam.rivera"))
    r = client.post(f"{BASE}/projects/{pid}/submit", headers=as_user("sam.rivera")).json()
    assert r["status"] == "triaged" and r["version"] == 2


def test_analyst_confirms_and_the_submitter_cannot(client):
    pid = new_project(client)
    run = client.post(f"{BASE}/projects/{pid}/submit", headers=as_user("sam.rivera")).json()["triage_run"]
    url = f"{BASE}/projects/{pid}/triage/{run}/decision"
    assert client.post(url, json={"decision": "confirm"}, headers=as_user("sam.rivera")).status_code == 403
    change = {"decision": "change", "changes": [
        {"action": "add", "item": "EU AI Act check", "reason": "Two candidates applied from Ireland"}]}
    r = client.post(url, json=change, headers=as_user("ana.patel"))
    assert r.status_code == 200, r.text
    assert client.post(url, json={"decision": "confirm"}, headers=as_user("ana.patel")).status_code == 409
    detail = client.get(f"{BASE}/projects/{pid}", headers=as_user("ana.patel")).json()
    assert detail["status"] == "confirmed"
    assert detail["triage"]["decision"]["changes"][0]["item"] == "EU AI Act check"
    assert detail["triage"]["result"]["assessments"]          # the rules' result is kept as it was
    # Confirmed intake is closed to edits.
    assert client.put(f"{BASE}/projects/{pid}/answers", json={"answers": FIXTURE["answers"]},
                      headers=as_user("sam.rivera")).status_code == 409


def test_removing_a_result_needs_it_to_exist(client):
    pid = new_project(client)
    run = client.post(f"{BASE}/projects/{pid}/submit", headers=as_user("sam.rivera")).json()["triage_run"]
    bad = {"decision": "change", "changes": [{"action": "remove", "rule": "NOT-A-RULE", "reason": "test"}]}
    assert client.post(f"{BASE}/projects/{pid}/triage/{run}/decision", json=bad,
                       headers=as_user("ana.patel")).status_code == 422


def test_submission_and_triage_are_audited(client):
    pid = new_project(client)
    client.post(f"{BASE}/projects/{pid}/submit", headers=as_user("sam.rivera"))
    events = client.get(f"{BASE}/audit", headers=as_user("ana.patel")).json()
    ran = next(e for e in events if e["action"] == "triage.ran" and e["payload"]["project"] == pid)
    assert ran["actor_type"] == "system" and ran["on_behalf_of"]
    assert "ccpa_risk_assessment" in ran["payload"]["assessments"]
    assert any(e["action"] == "intake.submitted" and e["object_id"] == pid for e in events)


def test_submissions_and_results_cannot_be_rewritten(superuser):
    with psycopg.connect(settings.app_dsn, row_factory=dict_row) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(HARBOR),))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE intake_submission SET answers = '{}'")
    # Even the owner cannot rewrite them: the triggers refuse.
    for sql in ("UPDATE intake_submission SET answers = '{}'", "DELETE FROM intake_submission",
                "UPDATE triage_run SET result = '{}'", "DELETE FROM triage_run"):
        with pytest.raises(psycopg.errors.RaiseException):
            superuser.execute(sql)
