"""The AI and ADMT risk assessment engine (WF-11, WF-15, WF-19, WF-20).

Everything here is deterministic. The template (content/assessment/template.yaml) says which
sections a report has and which verified provisions stand behind each. The method
(content/assessment/methodology.yaml) holds the five-level scale, the 5-by-5 matrix and the
approval routing. Both are content, so a tenant can substitute its own method later.

A section's content is stored as revisions that are never edited (WF-15): the agent's draft is
revision 1 and every reviewer change adds one. This module validates a proposed section,
checks it against the rest of the assessment, and computes everything a person must not type
in by hand: each risk's rating, the overall ratings, the routing level and what blocks a
decision to go ahead.
"""
from __future__ import annotations

import difflib
import hashlib
import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from . import content

ASSESSMENT_DIR = content.CONTENT_DIR.parent / "assessment"

Kind = Literal["text", "risk_register", "safeguards", "decision", "people", "approval"]
LEVELS = ("very_low", "low", "moderate", "high", "very_high")
Level = Literal["very_low", "low", "moderate", "high", "very_high"]
ROUTING = ("low", "medium", "high")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Template and method (content)
# ---------------------------------------------------------------------------

class Section(Strict):
    id: str
    number: str
    title: str
    kind: Kind
    provisions: list[str] = Field(min_length=1)
    in_regulator_report: bool
    editable: bool = True
    help: str


class FrameworkTag(Strict):
    id: str
    label: str
    help: str


class Template(Strict):
    id: str
    version: int
    title: str
    basis: list[str]
    sections: list[Section]
    framework: str
    framework_tags: list[FrameworkTag]

    def section(self, sid: str) -> Section | None:
        return next((s for s in self.sections if s.id == sid), None)

    def of_kind(self, kind: str) -> Section:
        return next(s for s in self.sections if s.kind == kind)

    @model_validator(mode="after")
    def unique(self) -> "Template":
        ids = [s.id for s in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("section ids must be unique")
        for kind in ("risk_register", "safeguards", "decision"):
            if sum(s.kind == kind for s in self.sections) != 1:
                raise ValueError(f"the template needs exactly one {kind} section")
        return self


class MethodLevel(Strict):
    id: Level
    label: str
    likelihood: str
    severity: str


class Routing(Strict):
    by_inherent_risk: dict[Level, Literal["low", "medium", "high"]]
    floor: dict[str, Any]


class Methodology(Strict):
    id: str
    version: str
    status: Literal["draft", "confirmed"]
    confirmed_by: str | None = None
    confirmed_on: date | None = None
    title: str
    sources: list[dict[str, str]]
    levels: list[MethodLevel]
    matrix: dict[Level, list[Level]]
    routing: Routing
    acceptance_needed_at: Level

    @model_validator(mode="after")
    def complete(self) -> "Methodology":
        if [lv.id for lv in self.levels] != list(LEVELS):
            raise ValueError(f"levels must be, in order, {LEVELS}")
        if set(self.matrix) != set(LEVELS) or any(len(row) != 5 for row in self.matrix.values()):
            raise ValueError("the matrix needs a row of five levels for each likelihood level")
        for row in self.matrix.values():
            if any(LEVELS.index(a) > LEVELS.index(b) for a, b in zip(row, row[1:])):
                raise ValueError("risk must not fall as severity rises")
        if set(self.routing.by_inherent_risk) != set(LEVELS):
            raise ValueError("routing.by_inherent_risk needs every level")
        if self.status == "confirmed" and not (self.confirmed_by and self.confirmed_on):
            raise ValueError("a confirmed method records who confirmed it and when")
        if self.routing.floor.get("default") not in ROUTING:
            raise ValueError("routing.floor.default must be low, medium or high")
        return self

    def rate(self, likelihood: str, severity: str) -> str:
        return self.matrix[likelihood][LEVELS.index(severity)]


@lru_cache
def _read(name: str) -> dict[str, Any]:
    return yaml.safe_load((ASSESSMENT_DIR / name).read_text(encoding="utf-8"))


def load_template(lib: content.Library) -> Template:
    t = Template.model_validate(_read("template.yaml"))
    index = lib.provision_index()
    for pid in t.basis + [p for s in t.sections for p in s.provisions]:
        if pid not in index:
            raise ValueError(f"template.yaml cites unknown provision {pid}")
    return t


def load_methodology(lib: content.Library) -> Methodology:
    m = Methodology.model_validate(_read("methodology.yaml"))
    rule_ids = {st.rule.id for st in lib.statuses}
    unknown = set(m.routing.floor.get("high_when_rules", [])) - rule_ids
    if unknown:
        raise ValueError(f"methodology.yaml routing floor names unknown rules {sorted(unknown)}")
    return m


def citations(lib: content.Library, provision_ids: list[str]) -> list[dict[str, Any]]:
    index = lib.provision_index()
    out = []
    for pid in provision_ids:
        pack, prov = index[pid]
        src = next(s for s in pack.sources if s.id == prov.source)
        out.append({"id": pid, "citation": prov.citation, "summary": prov.summary, "text": prov.text,
                    "location": prov.location, "source": src.title, "source_url": src.url,
                    "verified": content.provision_status(prov, lib.verifications[pack.id].get(pid)) is None})
    return out


# ---------------------------------------------------------------------------
# Section bodies
# ---------------------------------------------------------------------------

class TextBody(Strict):
    text: str = Field(max_length=20000)


class Risk(Strict):
    id: str = Field(pattern=r"^r[0-9]{1,3}$")
    title: str = Field(min_length=3, max_length=300)
    harm: str | None = None                        # harm taxonomy entry (WF-25 slice)
    source_and_cause: str = Field(min_length=3, max_length=4000)   # § 7152(a)(5): sources and causes
    affected: str | None = Field(None, max_length=1000)
    framework_tags: list[str] = []                 # NIST AI RMF characteristics: a reference, not law
    likelihood: Level
    severity: Level
    residual_likelihood: Level | None = None
    residual_severity: Level | None = None

    @model_validator(mode="after")
    def residual_is_paired_and_not_worse(self) -> "Risk":
        if (self.residual_likelihood is None) != (self.residual_severity is None):
            raise ValueError(f"{self.id}: rate both residual likelihood and residual severity, or neither")
        if self.residual_likelihood is not None:
            if LEVELS.index(self.residual_likelihood) > LEVELS.index(self.likelihood) \
                    or LEVELS.index(self.residual_severity) > LEVELS.index(self.severity):
                raise ValueError(f"{self.id}: safeguards cannot make a risk more likely or more severe; "
                                 "if the risk is worse than first rated, change the rating without safeguards")
        return self


class RiskRegister(Strict):
    risks: list[Risk] = []


class Safeguard(Strict):
    id: str = Field(pattern=r"^s[0-9]{1,3}$")
    title: str = Field(min_length=3, max_length=300)
    description: str = Field("", max_length=4000)
    status: Literal["planned", "in_place"] = "planned"
    owner: str | None = Field(None, max_length=200)
    addresses: list[str] = Field(min_length=1)    # risk ids this safeguard reduces

    @field_validator("addresses")
    @classmethod
    def no_repeats(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("list each risk once")
        return v


class Safeguards(Strict):
    safeguards: list[Safeguard] = []


class DecisionBody(Strict):
    initiate: Literal["yes", "no", "undecided"]
    rationale: str = Field("", max_length=4000)


class Person(Strict):
    name: str = Field(min_length=1, max_length=200)
    position: str = Field(min_length=1, max_length=200)
    provided: str | None = Field(None, max_length=1000)


class People(Strict):
    people: list[Person] = []


BODY_MODELS: dict[str, type[BaseModel]] = {
    "text": TextBody, "risk_register": RiskRegister, "safeguards": Safeguards,
    "decision": DecisionBody, "people": People,
}


class Rejected(ValueError):
    """A proposed section was refused; .problems says why, in plain language."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def _messages(exc: ValidationError) -> list[str]:
    out = []
    for e in exc.errors():
        where = ".".join(str(x) for x in e["loc"])
        msg = e["msg"].removeprefix("Value error, ")
        out.append(f"{where}: {msg}" if where else msg)
    return out


def parse(section: Section, body: dict[str, Any], tags: set[str],
          harm_ids: frozenset[str] | set[str] = frozenset()) -> dict[str, Any]:
    """Validate one section's body on its own. Returns it in normal form."""
    if not section.editable:
        raise Rejected([f"{section.title} is filled in by the approval steps and cannot be edited"])
    try:
        model = BODY_MODELS[section.kind].model_validate(body)
    except ValidationError as exc:
        raise Rejected(_messages(exc)) from exc
    problems = []
    if isinstance(model, RiskRegister):
        ids = [r.id for r in model.risks]
        if len(ids) != len(set(ids)):
            problems.append("each risk needs its own id")
        for r in model.risks:
            bad = set(r.framework_tags) - tags
            if bad:
                problems.append(f"{r.id}: unknown framework tags {sorted(bad)}")
            if r.harm is not None and r.harm not in harm_ids:
                problems.append(f"{r.id}: {r.harm} is not on the signed-off harm list")
    if isinstance(model, Safeguards):
        ids = [s.id for s in model.safeguards]
        if len(ids) != len(set(ids)):
            problems.append("each safeguard needs its own id")
    if problems:
        raise Rejected(problems)
    return model.model_dump(mode="json")


# ---------------------------------------------------------------------------
# The whole assessment
# ---------------------------------------------------------------------------

def floor_from_triage(result: dict[str, Any], decision: dict[str, Any] | None,
                      method: Methodology) -> tuple[str, list[str]]:
    """C5: the triage category sets the routing floor. Rules the analyst set aside do not count."""
    removed = {c["rule"] for c in (decision or {}).get("changes", []) if c.get("action") == "remove"}
    matched = {e["rule"] for k in ("classifications", "obligations") for e in result.get(k, [])}
    matched |= {t["rule"] for a in result.get("assessments", []) for t in a["triggered_by"]}
    matched -= removed
    high = sorted(matched & set(method.routing.floor.get("high_when_rules", [])))
    return ("high", high) if high else (method.routing.floor["default"], [])


def check(state: dict[str, dict[str, Any] | None], template: Template, method: Methodology,
          acceptances: list[dict[str, Any]]) -> list[str]:
    """Problems that would make this combination of sections inconsistent. Empty means fine."""
    risks = (state.get(template.of_kind("risk_register").id) or {}).get("risks", [])
    safeguards = (state.get(template.of_kind("safeguards").id) or {}).get("safeguards", [])
    decision = state.get(template.of_kind("decision").id)
    risk_ids = {r["id"] for r in risks}
    problems = []
    covered: set[str] = set()
    for s in safeguards:
        missing = [rid for rid in s["addresses"] if rid not in risk_ids]
        if missing:
            problems.append(f"safeguard {s['id']} addresses risks that are not in the register: {', '.join(missing)}")
        covered |= set(s["addresses"])
    for r in risks:
        if r.get("residual_likelihood") and r["id"] not in covered:
            problems.append(f"risk {r['id']} has a rating with safeguards, but no safeguard addresses it")
    if decision and decision["initiate"] == "yes":
        for b in blockers(risks, method, acceptances):
            problems.append(b)
    return problems


def blockers(risks: list[dict[str, Any]], method: Methodology, acceptances: list[dict[str, Any]]) -> list[str]:
    """WF-20: what stands in the way of a decision to go ahead."""
    out = []
    accepted = {a["risk"] for a in acceptances}
    bar = LEVELS.index(method.acceptance_needed_at)
    for r in risks:
        if not r.get("residual_likelihood"):
            out.append(f"risk {r['id']} has not been rated with safeguards yet")
            continue
        residual = method.rate(r["residual_likelihood"], r["residual_severity"])
        if LEVELS.index(residual) >= bar and r["id"] not in accepted:
            out.append(f"risk {r['id']} is still {residual.replace('_', ' ')} with safeguards; "
                       "the DPO must record a risk acceptance before the business can decide to go ahead")
    return out


def derive(state: dict[str, dict[str, Any] | None], template: Template, method: Methodology,
           floor: str, acceptances: list[dict[str, Any]]) -> dict[str, Any]:
    """Everything computed from the sections: ratings, routing and blockers."""
    risks = (state.get(template.of_kind("risk_register").id) or {}).get("risks", [])
    rated = []
    for r in risks:
        inherent = method.rate(r["likelihood"], r["severity"])
        residual = (method.rate(r["residual_likelihood"], r["residual_severity"])
                    if r.get("residual_likelihood") else None)
        rated.append({"risk": r["id"], "inherent": inherent, "residual": residual})

    def highest(key: str) -> str | None:
        vals = [x[key] for x in rated if x[key]]
        return max(vals, key=LEVELS.index) if vals else None

    overall_inherent, overall_residual = highest("inherent"), highest("residual")
    by_score = method.routing.by_inherent_risk[overall_inherent] if overall_inherent else "low"
    routing = max(floor, by_score, key=ROUTING.index)
    empty = [s.id for s in template.sections if s.editable and not state.get(s.id)]
    return {
        "ratings": rated,
        "overall_inherent": overall_inherent,
        "overall_residual": overall_residual,
        "routing": {"level": routing, "floor": floor, "from_score": by_score,
                    "raised_by_score": ROUTING.index(by_score) > ROUTING.index(floor)},
        "proceed_blockers": blockers(risks, method, acceptances),
        "consistency_problems": check(state, template, method, acceptances),
        "sections_not_started": empty,
    }


# ---------------------------------------------------------------------------
# Change history (WF-15)
# ---------------------------------------------------------------------------

def digest(body: dict[str, Any] | None) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def diff(kind: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    """What changed between two revisions of a section, in a form a reviewer can read."""
    before, after = before or {}, after or {}
    if kind == "text":
        lines = list(difflib.unified_diff((before.get("text") or "").splitlines(),
                                          (after.get("text") or "").splitlines(), lineterm="", n=1))
        return {"text": lines[2:]}
    key = {"risk_register": "risks", "safeguards": "safeguards", "people": "people"}.get(kind)
    if key is None:
        return {"changed": {k: {"from": before.get(k), "to": after.get(k)}
                            for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)}}
    ident = "name" if kind == "people" else "id"
    old = {i[ident]: i for i in before.get(key, [])}
    new = {i[ident]: i for i in after.get(key, [])}
    changed = {}
    for k in sorted(set(old) & set(new)):
        fields = {f: {"from": old[k].get(f), "to": new[k].get(f)}
                  for f in sorted(set(old[k]) | set(new[k])) if old[k].get(f) != new[k].get(f)}
        if fields:
            changed[k] = fields
    return {"added": sorted(set(new) - set(old)), "removed": sorted(set(old) - set(new)), "changed": changed}
