"""Triage (WF-05): the verified rules, evaluated by Open Policy Agent, decide what applies.

Classification rules set derived facts ("the system is ADMT", "the decision is
consequential"), and other rules test those facts. So triage runs in rounds: evaluate the
answers plus the facts the last round derived, derive them again, and stop when a round
derives exactly what the one before did. The last round's matches are the result. Every result carries its rule's
plain-language explanation and the citations behind it (the rule's provisions and the
definitions behind the questions it tested), with the content versions used (CNT-02).

No model is involved; the same answers always give the same result.
"""
from __future__ import annotations

from typing import Any, Callable

import httpx

from . import content
from .config import settings

Evaluate = Callable[[dict[str, Any]], list[dict[str, Any]]]


class PolicyEngineUnavailable(RuntimeError):
    pass


def opa_evaluate(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Ask OPA which loaded rules match these facts."""
    try:
        r = httpx.post(f"{settings.opa_url}/v1/data/opendpo/triage/results",
                       json={"input": {"facts": facts}}, timeout=5)
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise PolicyEngineUnavailable("the policy engine could not be reached, so triage did not run") from exc
    return r.json().get("result") or []


def run(lib: content.Library, answers: dict[str, Any], evaluate: Evaluate = opa_evaluate) -> dict[str, Any]:
    statuses = {st.rule.id: st for st in lib.statuses}
    limit = sum(1 for st in lib.statuses if st.rule.kind == "classification") + 2
    # Each round evaluates the answers plus the facts the previous round derived, and derives
    # them afresh. Derived facts are recomputed, not accumulated, because a rule may test that a
    # derived fact is absent (CCPA ADMT requires no human involvement): a fact derived before
    # its blocker was known must drop out once it is. Stop when a round derives what the last did.
    derived: dict[str, Any] = {}
    since: dict[str, int] = {}
    matches: list[dict[str, Any]] = []
    rounds = 0
    for rounds in range(1, limit + 1):
        matches = evaluate({**answers, **derived})
        now: dict[str, Any] = {}
        setters: dict[str, list[str]] = {}
        for m in sorted(matches, key=lambda m: m["rule"]):
            if m["kind"] == "classification" and "set_fact" in m["result"]:
                fid = m["result"]["set_fact"]
                if fid in answers:
                    raise ValueError(f"{fid} is derived by the rules and cannot be answered directly")
                now.setdefault(fid, m["result"]["value"])
                setters.setdefault(fid, []).append(m["rule"])
        since = {f: since.get(f, rounds) if f in derived else rounds for f in now}
        if now == derived:
            break
        derived = now
    else:
        raise RuntimeError("triage did not settle; classification rules depend on each other in a cycle")
    facts_derived = {f: {"value": v, "set_by": setters[f][0], "also_set_by": setters[f][1:], "round": since[f]}
                     for f, v in derived.items()}

    index = lib.provision_index()

    def cite(pid: str) -> dict[str, Any]:
        owner, prov = index[pid]
        src = next(s for s in owner.sources if s.id == prov.source)
        return {"id": pid, "citation": prov.citation, "summary": prov.summary, "location": prov.location,
                "source": src.title, "source_url": src.url}

    def explain(m: dict[str, Any]) -> dict[str, Any]:
        st = statuses[m["rule"]]
        return {"rule": m["rule"], "pack": m["pack"], "pack_version": m["pack_version"], "kind": m["kind"],
                "title": st.rule.title, "result": m["result"], "explanation": st.rule.explanation,
                "facts_tested": sorted(st.rule.when.facts()),
                "citations": [cite(pid) for pid in st.pack.citations(st.rule)]}

    explained = [explain(m) for m in sorted(matches, key=lambda m: (m["pack"], m["rule"]))]
    assessments: dict[str, dict[str, Any]] = {}
    for e in explained:
        if e["kind"] == "trigger" and "assessment" in e["result"]:
            a = assessments.setdefault(e["result"]["assessment"], {"assessment": e["result"]["assessment"],
                                                                   "pack": e["pack"], "triggered_by": []})
            a["triggered_by"].append(e)
    used_packs = {e["pack"] for e in explained}
    return {
        "classifications": [e for e in explained if e["kind"] == "classification"],
        "assessments": list(assessments.values()),
        "obligations": [e for e in explained if e["kind"] in ("obligation", "applicability")],
        "derived_facts": facts_derived,
        "rounds": rounds,
        "not_run": [{"rule": st.rule.id, "pack": st.pack.id, "title": st.rule.title, "problems": st.problems}
                    for st in lib.statuses if not st.usable],
        "content_versions": lib.versions(),
        "packs_with_results": sorted(used_packs),
    }


def summary(result: dict[str, Any]) -> dict[str, Any]:
    """The part of a triage result worth putting in the audit log."""
    return {"assessments": [a["assessment"] for a in result["assessments"]],
            "obligations": [o["rule"] for o in result["obligations"]],
            "classifications": [c["rule"] for c in result["classifications"]],
            "rules_not_run": len(result["not_run"])}
