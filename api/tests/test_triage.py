"""Intake form and triage, without the database.

The Harbor fixture is the preview walkthrough. Triage is checked twice: with every
rule as drafted (so the Colorado and NYC logic is exercised before its sign-off) and
with the gate as it stands, where only verified rules may run.

Rules are evaluated by the real policy/triage.rego through OPA when a server is
reachable at OPENDPO_OPA_URL (CI starts one); otherwise by the Python mirror in
opendpo.conditions, and test_python_mirror_matches_rego is skipped.
"""
import copy
import json
from pathlib import Path

import httpx
import pytest

from opendpo import content, intake, triage
from opendpo.conditions import holds
from opendpo.config import settings

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "harbor_resume_screener.json").read_text())


def all_rules_usable() -> content.Library:
    lib = content.load()
    for st in lib.statuses:
        st.usable, st.problems = True, []
    return lib


def python_evaluator(lib: content.Library):
    def evaluate(facts):
        return [{"rule": s.rule.id, "pack": s.pack.id, "pack_version": s.pack.version, "kind": s.rule.kind,
                 "result": s.rule.result} for s in lib.usable_rules if holds(s.rule.when, facts)]
    return evaluate


def opa_available() -> bool:
    try:
        return httpx.get(f"{settings.opa_url}/health", timeout=1).status_code == 200
    except httpx.HTTPError:
        return False


def opa_evaluator(lib: content.Library):
    httpx.put(f"{settings.opa_url}/v1/data/opendpo/content", json=lib.opa_data(), timeout=5).raise_for_status()
    return triage.opa_evaluate


@pytest.fixture
def evaluator():
    """The real Rego when OPA is up; content is restored to the gate's view afterwards."""
    if not opa_available():
        yield python_evaluator
        return
    yield opa_evaluator
    httpx.put(f"{settings.opa_url}/v1/data/opendpo/content", json=content.load().opa_data(), timeout=5)


def facts() -> dict:
    return {**FIXTURE["scoping"], **FIXTURE["answers"]}


def names(result: dict) -> dict:
    return {"classifications": sorted(c["rule"] for c in result["classifications"]),
            "assessments": sorted(a["assessment"] for a in result["assessments"]),
            "obligations": sorted(o["rule"] for o in result["obligations"])}


# --- the form --------------------------------------------------------------------

def test_every_intake_question_in_the_packs_is_placed():
    lib = content.load()
    assert intake.unplaced(lib, intake.build(lib)) == []


def test_pack_questions_carry_their_definitions():
    form = intake.build(content.load())
    q = form.by_id()["co.influence.non_de_minimis"]
    assert [d["id"] for d in q.definitions] == ["co-6-1-1701-13"]
    assert "NON-DE MINIMIS" in q.definitions[0]["text"]
    prop = form.json_schema()["properties"]["co.influence.non_de_minimis"]
    assert prop["x-opendpo"]["definitions"][0]["citation"] == "C.R.S. § 6-1-1701(13)"


def test_harbor_fixture_is_a_complete_valid_intake():
    form = intake.build(content.load())
    assert form.validate(FIXTURE["answers"]) == []
    assert form.prune(FIXTURE["answers"]) == FIXTURE["answers"]


def test_branches_follow_the_answers():
    form = intake.build(content.load())
    no_ai = {**FIXTURE["answers"], "project.uses_ai": "no"}
    shown = {q.id for q in form.visible(no_ai)}
    assert "ai.role" not in shown and "nyc.tool.screens" not in shown and "co.tech.generates_output" not in shown
    assert "data.sells_or_shares" in shown            # CCPA data questions do not depend on AI
    ca_only = {**FIXTURE["answers"], "project.locations": ["US-CA"]}
    shown = {q.id for q in form.visible(ca_only)}
    assert "ai.role" in shown and not any(i.startswith(("co.", "nyc.")) for i in shown)
    # Answers to hidden questions are dropped, not submitted.
    assert not any(k.startswith("nyc.") for k in form.prune(ca_only))


def test_missing_and_malformed_answers_are_reported():
    form = intake.build(content.load())
    answers = copy.deepcopy(FIXTURE["answers"])
    del answers["ai.role"]
    answers["nyc.tool.output_use"] = "always"
    answers["project.go_live"] = "next spring"
    problems = {p["question"] for p in form.validate(answers)}
    assert {"ai.role", "nyc.tool.output_use", "project.go_live"} <= problems


def test_reviewer_questions_appear_only_when_the_ai_role_needs_them():
    form = intake.build(content.load())
    assisting = {**FIXTURE["answers"], "ai.role": "assists"}
    shown = {q.id for q in form.visible(assisting)}
    assert "ai.reviewer_can_change" not in shown


# --- triage ----------------------------------------------------------------------

def test_harbor_triage_with_every_rule_as_drafted(evaluator):
    lib = all_rules_usable()
    result = triage.run(lib, facts(), evaluator(lib))
    assert names(result) == FIXTURE["expected"]
    assert result["derived_facts"]["co.covered_admt"]["round"] == 2     # needs the round-1 classifications
    assert result["not_run"] == []


def test_harbor_triage_runs_only_verified_rules(evaluator):
    lib = content.load()
    result = triage.run(lib, facts(), evaluator(lib))
    got = names(result)
    for kind, expected in FIXTURE["expected"].items():
        assert set(got[kind]) == {r for r in expected if r.startswith("CCPA-") or r.startswith("ccpa")}
    unverified = {r["rule"] for r in result["not_run"]}
    assert {"CO-DEPLOYER-NOTICE", "NYC-BIAS-AUDIT"} <= unverified


def test_results_carry_explanations_and_citations(evaluator):
    lib = all_rules_usable()
    result = triage.run(lib, facts(), evaluator(lib))
    notice = next(o for o in result["obligations"] if o["rule"] == "CO-DEPLOYER-NOTICE")
    assert notice["explanation"]
    cited = [c["id"] for c in notice["citations"]]
    assert cited[0] == "co-6-1-1704-1-2"
    assert "co-6-1-1701-4" in cited                     # the definition behind a question it tested
    assert all(c["source_url"].startswith("https://") for c in notice["citations"])
    assert result["content_versions"]["us-co-sb26-189"] == "0.1.0"


def test_human_involvement_takes_the_system_out_of_ccpa_admt(evaluator):
    lib = all_rules_usable()
    f = {**facts(), "ai.reviewer_reviews_other_info": True}
    got = names(triage.run(lib, f, evaluator(lib)))
    assert "CCPA-CLASS-ADMT" not in got["classifications"]
    assert "ccpa_risk_assessment" not in got["assessments"]
    assert "CO-DEPLOYER-NOTICE" in got["obligations"]   # Colorado asks about influence, not replacement


def test_hipaa_exemption_does_not_reach_employment(evaluator):
    lib = all_rules_usable()
    f = {**facts(), "co.exempt.hipaa_covered_entity": True}
    assert "CO-DEPLOYER-NOTICE" in names(triage.run(lib, f, evaluator(lib)))["obligations"]
    f.update({"co.decision.domain": "healthcare"})
    assert "CO-DEPLOYER-NOTICE" not in names(triage.run(lib, f, evaluator(lib)))["obligations"]


def test_selection_tools_get_the_selection_rate_method(evaluator):
    lib = all_rules_usable()
    f = {**facts(), "nyc.tool.output_kinds": ["selects_or_classifies"]}
    got = names(triage.run(lib, f, evaluator(lib)))["obligations"]
    assert "NYC-BIAS-AUDIT-SELECTION" in got and "NYC-BIAS-AUDIT-SCORING" not in got


def test_triage_is_deterministic(evaluator):
    lib = all_rules_usable()
    assert triage.run(lib, facts(), evaluator(lib)) == triage.run(lib, facts(), evaluator(lib))


@pytest.mark.skipif(not opa_available(), reason="needs an OPA server to compare against")
def test_python_mirror_matches_rego():
    """The Python copy used for showing questions agrees with Rego on every rule."""
    lib = all_rules_usable()
    variants = [facts(), {**facts(), "project.uses_ai": "no"}, {**facts(), "co.decision.domain": "other"},
                {**facts(), "ai.role": "assists", "nyc.tool.output_use": "other"}, {}]
    rego = opa_evaluator(lib)
    try:
        for f in variants:
            key = lambda r: r["rule"]  # noqa: E731
            assert sorted(rego(f), key=key) == sorted(python_evaluator(lib)(f), key=key)
    finally:
        httpx.put(f"{settings.opa_url}/v1/data/opendpo/content", json=content.load().opa_data(), timeout=5)
