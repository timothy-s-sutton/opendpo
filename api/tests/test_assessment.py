"""The assessment engine (WF-11, WF-15, WF-19, WF-20): the template and method as content,
scoring and routing, consistency between risks and safeguards, the block on going ahead,
and revision history through the API. The API tests need the database and OPA, like
test_intake_api.py."""
import psycopg
import pytest

from opendpo import assessment as engine
from opendpo import content, main
from opendpo.config import settings
from opendpo.db import tenant_tx

from .conftest import HARBOR, as_user
from .test_triage import FIXTURE, all_rules_usable

BASE = f"/api/tenants/{HARBOR}"


# ---------------------------------------------------------------------------
# Engine, without the database
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tpl():
    return engine.load_template(content.load())


@pytest.fixture(scope="module")
def method():
    return engine.load_methodology(content.load())


def risk(rid="r1", lik="high", sev="high", res=None, **extra):
    r = {"id": rid, "title": "Qualified applicants screened out", "source_and_cause": "Model trained on past hires",
         "likelihood": lik, "severity": sev, **extra}
    if res:
        r["residual_likelihood"], r["residual_severity"] = res
    return r


def test_template_sections_follow_7152(tpl):
    assert [s.id for s in tpl.sections] == ["purpose", "personal_information", "operations", "benefits", "risks",
                                           "safeguards", "decision", "contributors", "approval"]
    assert tpl.section("risks").provisions == ["ccpa-7152-a-5"]
    assert not tpl.section("benefits").in_regulator_report and tpl.section("safeguards").in_regulator_report
    assert not tpl.section("approval").editable


def test_unknown_provision_is_refused(monkeypatch):
    raw = dict(engine._read("template.yaml"))
    raw["basis"] = ["ccpa-9999"]
    monkeypatch.setattr(engine, "_read", lambda name: raw)
    with pytest.raises(ValueError, match="ccpa-9999"):
        engine.load_template(content.load())


def test_method_is_confirmed(method):
    assert method.status == "confirmed" and method.confirmed_by == "Tim Sutton"
    raw = {**engine._read("methodology.yaml"), "confirmed_by": None}
    with pytest.raises(ValueError, match="who confirmed it"):
        engine.Methodology.model_validate(raw)


def test_matrix(method):
    assert method.rate("very_high", "very_high") == "very_high"
    assert method.rate("moderate", "high") == "moderate"
    assert method.rate("low", "very_high") == "moderate"
    assert method.rate("very_low", "very_low") == "very_low"


def test_routing_floor_holds_and_score_can_raise_it(tpl, method):
    low = {"risks": {"risks": [risk(lik="low", sev="low")]}}
    d = engine.derive(low, tpl, method, "high", [])
    assert d["routing"] == {"level": "high", "floor": "high", "from_score": "low", "raised_by_score": False}
    d = engine.derive({"risks": {"risks": [risk()]}}, tpl, method, "low", [])
    assert d["routing"]["level"] == "high" and d["routing"]["raised_by_score"]
    assert d["overall_inherent"] == "high" and d["overall_residual"] is None


def test_residual_must_be_paired_and_not_worse(tpl):
    tags = {t.id for t in tpl.framework_tags}
    with pytest.raises(engine.Rejected, match="both residual"):
        engine.parse(tpl.section("risks"), {"risks": [{**risk(), "residual_likelihood": "low"}]}, tags)
    with pytest.raises(engine.Rejected, match="more likely or more severe"):
        engine.parse(tpl.section("risks"), {"risks": [risk(lik="low", res=("moderate", "low"))]}, tags)
    with pytest.raises(engine.Rejected, match="unknown framework tags"):
        engine.parse(tpl.section("risks"), {"risks": [risk(framework_tags=["fair", "vibes"])]}, tags)
    ok = engine.parse(tpl.section("risks"), {"risks": [risk(framework_tags=["fair"])]}, tags)
    assert ok["risks"][0]["residual_likelihood"] is None


def test_risks_and_safeguards_must_line_up(tpl, method):
    state = {"risks": {"risks": [risk(res=("moderate", "high"))]},
             "safeguards": {"safeguards": [{"id": "s1", "title": "Bias audit", "addresses": ["r2"]}]}}
    problems = engine.check(state, tpl, method, [])
    assert any("not in the register: r2" in p for p in problems)
    assert any("no safeguard addresses it" in p for p in problems)
    state["safeguards"]["safeguards"][0]["addresses"] = ["r1"]
    assert engine.check(state, tpl, method, []) == []


def test_going_ahead_needs_acceptance_of_high_residual_risk(tpl, method):
    state = {"risks": {"risks": [risk(res=("high", "high"))]},
             "safeguards": {"safeguards": [{"id": "s1", "title": "Human review", "addresses": ["r1"]}]},
             "decision": {"initiate": "yes", "rationale": ""}}
    assert any("risk acceptance" in p for p in engine.check(state, tpl, method, []))
    assert engine.check(state, tpl, method, [{"risk": "r1"}]) == []
    state["decision"]["initiate"] = "no"
    assert engine.check(state, tpl, method, []) == []


def test_floor_from_harbor_triage(method):
    from opendpo import triage
    from .test_triage import python_evaluator
    lib = all_rules_usable()
    result = triage.run(lib, {**FIXTURE["scoping"], **FIXTURE["answers"]}, python_evaluator(lib))
    assert engine.floor_from_triage(result, None, method) == ("high", ["CCPA-RA-ADMT", "CO-CLASS-COVERED-ADMT"])
    # An analyst who sets both rules aside lowers the floor.
    decision = {"changes": [{"action": "remove", "rule": "CCPA-RA-ADMT"},
                            {"action": "remove", "rule": "CO-CLASS-COVERED-ADMT"}]}
    assert engine.floor_from_triage(result, decision, method) == ("low", [])


def test_diff(tpl):
    assert engine.diff("text", {"text": "a\nb"}, {"text": "a\nc"})["text"] == ["@@ -1,2 +1,2 @@", " a", "-b", "+c"]
    d = engine.diff("risk_register", {"risks": [risk(), risk("r2")]}, {"risks": [risk(sev="moderate"), risk("r3")]})
    assert d == {"added": ["r3"], "removed": ["r2"], "changed": {"r1": {"severity": {"from": "high", "to": "moderate"}}}}


# ---------------------------------------------------------------------------
# Through the API
# ---------------------------------------------------------------------------

@pytest.fixture
def rules_loaded():
    lib = all_rules_usable()
    saved, main._library = main._library, lib
    main.publish_content_to_policy_engine(retries=3)
    yield
    main._library = saved
    main.publish_content_to_policy_engine(retries=3)


def confirmed_project(client):
    pid = client.post(f"{BASE}/projects", json={"answers": FIXTURE["answers"]}, headers=as_user("sam.rivera")).json()["id"]
    run = client.post(f"{BASE}/projects/{pid}/submit", headers=as_user("sam.rivera")).json()["triage_run"]
    r = client.post(f"{BASE}/projects/{pid}/triage/{run}/decision", json={"decision": "confirm"},
                    headers=as_user("ana.patel"))
    assert r.status_code == 200, r.text
    return pid


@pytest.fixture
def opened(client, rules_loaded):
    pid = confirmed_project(client)
    r = client.post(f"{BASE}/projects/{pid}/assessments", json={}, headers=as_user("ana.patel"))
    assert r.status_code == 201, r.text
    return r.json()["id"]


def save(client, aid, section, body, base, who="ana.patel"):
    return client.put(f"{BASE}/assessments/{aid}/sections/{section}", json={"body": body, "base_revision": base},
                      headers=as_user(who))


def test_assessment_needs_confirmed_triage(client, rules_loaded):
    pid = client.post(f"{BASE}/projects", json={"answers": FIXTURE["answers"]}, headers=as_user("sam.rivera")).json()["id"]
    client.post(f"{BASE}/projects/{pid}/submit", headers=as_user("sam.rivera"))
    r = client.post(f"{BASE}/projects/{pid}/assessments", json={}, headers=as_user("ana.patel"))
    assert r.status_code == 409


def test_open_assessment(client, opened):
    a = client.get(f"{BASE}/assessments/{opened}", headers=as_user("carla.mendes")).json()
    assert a["type"] == "ccpa_risk_assessment" and a["status"] == "draft"
    assert a["floor_rules"] == ["CCPA-RA-ADMT", "CO-CLASS-COVERED-ADMT"]
    assert a["computed"]["routing"]["level"] == "high"
    risks = next(s for s in a["sections"] if s["id"] == "risks")
    assert risks["what_the_law_says"][0]["citation"] == "Cal. Code Regs. tit. 11, § 7152(a)(5)"
    assert len(a["computed"]["sections_not_started"]) == 8
    assert a["methodology"]["id"] == "opendpo-default-5x5"


def test_only_one_assessment_per_triage_run(client, opened):
    pid = client.get(f"{BASE}/assessments/{opened}", headers=as_user("ana.patel")).json()["project_id"]
    r = client.post(f"{BASE}/projects/{pid}/assessments", json={}, headers=as_user("ana.patel"))
    assert r.status_code == 409 and r.json()["detail"]["assessment"] == opened


def test_who_may_open_read_and_edit(client, opened, rules_loaded):
    pid = confirmed_project(client)
    assert client.post(f"{BASE}/projects/{pid}/assessments", json={}, headers=as_user("sam.rivera")).status_code == 403
    assert client.get(f"{BASE}/assessments/{opened}", headers=as_user("avery.shaw")).status_code == 200   # auditor
    assert client.get(f"{BASE}/assessments/{opened}", headers=as_user("sam.rivera")).status_code == 403   # submitter
    assert save(client, opened, "purpose", {"text": "x"}, 0, who="avery.shaw").status_code == 403


def test_edits_build_a_history(client, opened):
    assert save(client, opened, "purpose", {"text": "Rank applicants for driver roles."}, 0).json()["revision"] == 1
    # Saving from a stale page is refused, so a newer edit is never overwritten.
    assert save(client, opened, "purpose", {"text": "Something else"}, 0).status_code == 409
    assert save(client, opened, "purpose", {"text": "Rank applicants so recruiters call the strongest first."}, 1,
                who="carla.mendes").json()["revision"] == 2
    assert save(client, opened, "purpose", {"text": "Rank applicants so recruiters call the strongest first."}, 2
                ).json() == {"saved": False, "revision": 2, "message": "nothing changed"}
    h = client.get(f"{BASE}/assessments/{opened}/sections/purpose/revisions", headers=as_user("avery.shaw")).json()
    assert [r["author_name"] for r in h["revisions"]] == ["Ana Patel", "Carla Mendes"]
    assert "-Rank applicants for driver roles." in h["since_first"]["text"]
    a = client.get(f"{BASE}/assessments/{opened}", headers=as_user("ana.patel")).json()
    purpose = next(s for s in a["sections"] if s["id"] == "purpose")
    assert purpose["revision"] == 2 and purpose["last_edited_by"] == "Carla Mendes"


def test_risk_register_safeguards_and_decision(client, opened):
    r1 = risk(framework_tags=["fair"])
    assert save(client, opened, "risks", {"risks": [r1]}, 0).status_code == 200
    # A rating with safeguards needs a safeguard that addresses the risk.
    rated = {**r1, "residual_likelihood": "moderate", "residual_severity": "high"}
    r = save(client, opened, "risks", {"risks": [rated]}, 1)
    assert r.status_code == 422 and "no safeguard addresses it" in r.json()["detail"]["problems"][0]
    sg = {"safeguards": [{"id": "s1", "title": "Independent bias audit before use", "addresses": ["r1"]}]}
    assert save(client, opened, "safeguards", sg, 0).status_code == 200
    assert save(client, opened, "risks", {"risks": [rated]}, 1).status_code == 200
    # A risk a safeguard still points to cannot simply disappear.
    r = save(client, opened, "risks", {"risks": []}, 2)
    assert r.status_code == 422 and "not in the register: r1" in r.json()["detail"]["problems"][0]
    a = client.get(f"{BASE}/assessments/{opened}", headers=as_user("ana.patel")).json()
    assert a["computed"]["ratings"] == [{"risk": "r1", "inherent": "high", "residual": "moderate"}]
    assert a["computed"]["proceed_blockers"] == []
    assert save(client, opened, "decision", {"initiate": "yes", "rationale": "Safeguards in place"}, 0).status_code == 200
    # Raising the residual risk to high is refused while the decision is to go ahead.
    worse = {**rated, "residual_likelihood": "high"}
    r = save(client, opened, "risks", {"risks": [worse]}, 2)
    assert r.status_code == 422 and "risk acceptance" in r.json()["detail"]["problems"][0]


def test_approval_section_is_not_edited_by_hand(client, opened):
    r = save(client, opened, "approval", {"text": "Approved"}, 0)
    assert r.status_code == 422 and "approval steps" in r.json()["detail"]["problems"][0]


def test_bad_body_is_explained(client, opened):
    r = save(client, opened, "risks", {"risks": [{"id": "risk-one", "likelihood": "huge"}]}, 0)
    assert r.status_code == 422
    assert any("risks.0.likelihood" in p for p in r.json()["detail"]["problems"])


def test_edits_are_audited(client, opened):
    save(client, opened, "benefits", {"text": "Recruiters reach strong applicants sooner."}, 0)
    with tenant_tx(HARBOR) as conn:
        e = conn.execute("""SELECT action, payload FROM audit_event WHERE object_id = %s ORDER BY seq""",
                         (opened,)).fetchall()
    assert [x["action"] for x in e] == ["assessment.created", "assessment.section_revised"]
    assert e[0]["payload"]["routing_floor"] == "high" and e[1]["payload"]["section"] == "benefits"


def test_revisions_and_basis_cannot_be_changed(client, opened):
    save(client, opened, "purpose", {"text": "Rank applicants."}, 0)
    with psycopg.connect(settings.owner_dsn) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE assessment_revision SET body = '{}' WHERE assessment_id = %s", (opened,))
    with psycopg.connect(settings.owner_dsn) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE assessment SET routing_floor = 'low' WHERE id = %s", (opened,))
    with tenant_tx(HARBOR) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM assessment_revision WHERE assessment_id = %s", (opened,))
