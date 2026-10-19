"""Regulatory content packs and the verification gate (CNT-01, CNT-02, CNT-04).

A pack is a directory under content/packs/<pack id>/ with two files:

  pack.yaml          the provisions (verbatim primary text) and the rules built on them
  verification.yaml  one sign-off record per rule

A rule reaches the rules engine only when (1) every provision it cites has a
sign-off that its text matches the primary source, and (2) the rule itself has a
sign-off that its logic reads those provisions correctly. Each sign-off stores a
fingerprint of exactly what was checked; change the text or the logic, even by
one character, and that sign-off lapses until someone checks it again. Unverified rules stay visible, marked as
such, but cannot decide anything.

Command line:
    python -m opendpo.content status            show every rule and why it is or is not usable
    python -m opendpo.content fingerprint ID    print a provision's or rule's fingerprint for a sign-off
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTENT_DIR = Path(os.environ.get(
    "OPENDPO_CONTENT_DIR", Path(__file__).resolve().parents[2] / "content" / "packs"))

Lifecycle = Literal["proposed", "enacted", "effective", "superseded", "repealed"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Source(Strict):
    id: str
    title: str
    publisher: str
    url: str
    primary: bool = Field(description="True for statute, regulation or official publication")
    retrieved_on: date


class Provision(Strict):
    id: str
    citation: str                 # e.g. "Cal. Code Regs. tit. 11, § 7150(b)(1)"
    source: str                   # Source.id
    location: str | None = None   # page or section in the source document
    effective_from: date | None = None
    text: str                     # verbatim primary text
    summary: str                  # OpenDPO's plain-language summary

    @property
    def fingerprint(self) -> str:
        return text_fingerprint(self.text)


class Option(Strict):
    value: str
    label: str


class Fact(Strict):
    """A question asked in scoping or intake, and the definitions that govern its answer.
    The definitions are shown beside the question and cited in every explanation that uses it."""
    id: str
    question: str
    type: Literal["boolean", "choice", "multichoice", "number"]
    options: list[Option] | None = None
    defined_by: list[str] = []        # provision ids
    help: str | None = None
    asked_in: Literal["scoping", "intake", "inventory"] = "intake"
    pending: str | None = None        # why the governing definition is not yet in a pack

    @model_validator(mode="after")
    def options_match_type(self) -> "Fact":
        if self.type in ("choice", "multichoice") and not self.options:
            raise ValueError(f"fact {self.id}: a {self.type} fact needs options")
        if self.type in ("boolean", "number") and self.options:
            raise ValueError(f"fact {self.id}: a {self.type} fact takes no options")
        return self


class Condition(Strict):
    """A test on one fact, or a group of tests. Two levels of nesting at most,
    so the Rego evaluator stays simple enough for an auditor to read."""
    fact: str | None = None
    equals: Any = None
    in_: list[Any] | None = Field(None, alias="in")
    contains: Any = None
    at_least: float | None = None
    all: list["Condition"] | None = None
    any: list["Condition"] | None = None
    not_: "Condition | None" = Field(None, alias="not")

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    @model_validator(mode="after")
    def one_shape(self) -> "Condition":
        groups = [g for g in (self.all, self.any, self.not_) if g is not None]
        if self.fact is None and len(groups) != 1:
            raise ValueError("a condition is either a fact test or exactly one of all / any / not")
        if self.fact is not None and groups:
            raise ValueError("a fact test cannot also contain all / any / not")
        if self.fact is not None:
            tests = [t for t in (self.equals, self.in_, self.contains, self.at_least) if t is not None]
            if len(tests) != 1:
                raise ValueError(f"fact {self.fact!r} needs exactly one of equals / in / contains / at_least")
        return self

    def leaves(self) -> list["Condition"]:
        if self.fact is not None:
            return [self]
        kids = (self.all or []) + (self.any or []) + ([self.not_] if self.not_ else [])
        return [leaf for k in kids for leaf in k.leaves()]

    def values(self) -> list[Any]:
        if self.in_ is not None:
            return list(self.in_)
        return [v for v in (self.equals, self.contains) if v is not None]

    def depth(self) -> int:
        kids = (self.all or []) + (self.any or []) + ([self.not_] if self.not_ else [])
        return 1 + max((k.depth() for k in kids), default=0)

    def facts(self) -> set[str]:
        kids = (self.all or []) + (self.any or []) + ([self.not_] if self.not_ else [])
        return ({self.fact} if self.fact else set()).union(*(k.facts() for k in kids))


class Rule(Strict):
    id: str
    kind: Literal["applicability", "trigger", "obligation", "classification"]
    title: str
    provisions: list[str] = Field(min_length=1)
    when: Condition
    result: dict[str, Any]        # what the rule concludes, e.g. {"assessment": "ccpa_risk_assessment"}
    explanation: str              # plain-language reason, shown with citations

    @property
    def fingerprint(self) -> str:
        """Covers the rule's logic: what it cites, when it fires and what it concludes."""
        logic = {"provisions": sorted(self.provisions),
                 "when": self.when.model_dump(by_alias=True, exclude_none=True), "result": self.result}
        return hashlib.sha256(json.dumps(logic, sort_keys=True).encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def shallow(self) -> "Rule":
        if self.when.depth() > 3:
            raise ValueError(f"rule {self.id}: conditions may nest at most two groups deep")
        return self


class Pack(Strict):
    id: str
    title: str
    jurisdiction: str             # ISO 3166 code, e.g. US-CA (PLT-27)
    version: str                  # semantic version (UPD-01)
    lifecycle: Lifecycle
    as_of: date                   # USE-05
    supersedes: str | None = None
    sources: list[Source]
    provisions: list[Provision]
    facts: list[Fact] = []
    rules: list[Rule] = []

    def derived_facts(self) -> dict[str, str]:
        """Facts set by this pack's classification rules: fact id -> rule id."""
        return {r.result["set_fact"]: r.id for r in self.rules if r.kind == "classification" and "set_fact" in r.result}

    @model_validator(mode="after")
    def references_resolve(self) -> "Pack":
        source_ids = {s.id for s in self.sources}
        prov_ids = [p.id for p in self.provisions]
        if len(prov_ids) != len(set(prov_ids)):
            raise ValueError(f"pack {self.id}: duplicate provision ids")
        for p in self.provisions:
            if p.source not in source_ids:
                raise ValueError(f"provision {p.id}: unknown source {p.source}")
        rule_ids = [r.id for r in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError(f"pack {self.id}: duplicate rule ids")
        for r in self.rules:
            missing = set(r.provisions) - set(prov_ids)
            if missing:
                raise ValueError(f"rule {r.id}: cites unknown provisions {sorted(missing)}")
        facts = {f.id: f for f in self.facts}
        for f in self.facts:
            missing = set(f.defined_by) - set(prov_ids)
            if missing:
                raise ValueError(f"fact {f.id}: defined by unknown provisions {sorted(missing)}")
        derived = self.derived_facts()
        for r in self.rules:
            for leaf in r.when.leaves():
                if leaf.fact in derived:
                    continue
                f = facts.get(leaf.fact)
                if f is None:
                    raise ValueError(f"rule {r.id}: tests undeclared fact {leaf.fact!r}")
                allowed = {o.value for o in f.options or []}
                for v in leaf.values():
                    if f.type in ("choice", "multichoice") and v not in allowed:
                        raise ValueError(f"rule {r.id}: {v!r} is not an answer to {f.id}")
                    if f.type == "boolean" and not isinstance(v, bool):
                        raise ValueError(f"rule {r.id}: {f.id} is yes/no, not {v!r}")
        return self

    def citations(self, rule: "Rule") -> list[str]:
        """The rule's own provisions plus the definitions behind every fact it tests."""
        facts = {f.id: f for f in self.facts}
        out = list(rule.provisions)
        for fid in sorted(rule.when.facts()):
            for pid in (facts[fid].defined_by if fid in facts else []):
                if pid not in out:
                    out.append(pid)
        return out


class Verification(Strict):
    """A sign-off on either a provision's text (it matches the primary source) or a
    rule's logic (it reads the cited provisions correctly). Exactly one of the two."""
    provision: str | None = None
    rule: str | None = None
    fingerprint: str              # of the provision text, or of the rule logic, as checked
    verified_by: str
    verified_on: date
    method: str = "Compared word for word against the primary source"
    self_verified: bool = True    # USE-07: author and verifier are the same person
    note: str | None = None

    @model_validator(mode="after")
    def one_target(self) -> "Verification":
        if (self.provision is None) == (self.rule is None):
            raise ValueError("a verification record names either a provision or a rule")
        return self


def text_fingerprint(text: str) -> str:
    """SHA-256 of the text with whitespace runs collapsed, so line wrapping does not matter."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


@dataclass
class RuleStatus:
    rule: Rule
    pack: Pack
    usable: bool
    problems: list[str] = field(default_factory=list)


@dataclass
class Library:
    packs: list[Pack]
    verifications: dict[str, dict[str, Verification]]   # pack id -> provision id -> record
    statuses: list[RuleStatus]
    rule_verifications: dict[str, dict[str, Verification]] = field(default_factory=dict)

    @property
    def usable_rules(self) -> list[RuleStatus]:
        return [s for s in self.statuses if s.usable]

    def provision(self, pack_id: str, provision_id: str) -> Provision:
        pack = next(p for p in self.packs if p.id == pack_id)
        return next(p for p in pack.provisions if p.id == provision_id)

    def versions(self) -> dict[str, str]:
        """CNT-02: pack id -> version, recorded on every output that used them."""
        return {p.id: p.version for p in self.packs}

    def opa_data(self) -> dict[str, Any]:
        """Only usable rules, in the shape policy/triage.rego reads."""
        return {"rules": [
            {"id": s.rule.id, "pack": s.pack.id, "pack_version": s.pack.version, "kind": s.rule.kind,
             "when": s.rule.when.model_dump(by_alias=True, exclude_none=True),
             "result": s.rule.result, "citations": s.pack.citations(s.rule)}
            for s in self.usable_rules]}


def provision_status(p: Provision, record: Verification | None) -> str | None:
    """None if verified and current; otherwise the reason it is not."""
    if record is None:
        return f"{p.id} has not been verified against primary text"
    if record.fingerprint != p.fingerprint:
        return f"{p.id} changed after it was verified on {record.verified_on}; verify it again"
    return None


def load(directory: Path = CONTENT_DIR) -> Library:
    packs: list[Pack] = []
    verifications: dict[str, dict[str, Verification]] = {}
    rule_verifications: dict[str, dict[str, Verification]] = {}
    statuses: list[RuleStatus] = []
    if not directory.is_dir():
        return Library(packs, verifications, statuses)
    for pack_dir in sorted(d for d in directory.iterdir() if (d / "pack.yaml").is_file()):
        pack = Pack.model_validate(yaml.safe_load((pack_dir / "pack.yaml").read_text(encoding="utf-8")))
        if pack.id != pack_dir.name:
            raise ValueError(f"pack id {pack.id!r} must match its folder name {pack_dir.name!r}")
        vfile = pack_dir / "verification.yaml"
        raw = (yaml.safe_load(vfile.read_text(encoding="utf-8")) or []) if vfile.is_file() else []
        parsed = [Verification.model_validate(r) for r in raw]
        records = {v.provision: v for v in parsed if v.provision}
        rule_records = {v.rule: v for v in parsed if v.rule}
        unknown = (set(records) - {p.id for p in pack.provisions}) | (set(rule_records) - {r.id for r in pack.rules})
        if unknown:
            raise ValueError(f"{vfile}: records for unknown provisions or rules {sorted(unknown)}")
        sources = {s.id: s for s in pack.sources}
        for rule in pack.rules:
            problems = []
            for pid in pack.citations(rule):
                prov = next(p for p in pack.provisions if p.id == pid)
                if not sources[prov.source].primary:
                    problems.append(f"{pid} cites a secondary source; only primary text can be the citation of record")
                issue = provision_status(prov, records.get(pid))
                if issue:
                    problems.append(issue)
            rr = rule_records.get(rule.id)
            if rr is None:
                problems.append("the rule's reading of the law has not been verified")
            elif rr.fingerprint != rule.fingerprint:
                problems.append(f"the rule's logic changed after it was verified on {rr.verified_on}; verify it again")
            statuses.append(RuleStatus(rule, pack, not problems, problems))
        packs.append(pack)
        verifications[pack.id] = records
        rule_verifications[pack.id] = rule_records
    return Library(packs, verifications, statuses, rule_verifications)


def _cli() -> None:
    import sys

    lib = load()
    if len(sys.argv) >= 3 and sys.argv[1] == "fingerprint":
        for pack in lib.packs:
            for p in pack.provisions:
                if p.id == sys.argv[2]:
                    print(p.fingerprint)
                    return
            for r in pack.rules:
                if r.id == sys.argv[2]:
                    print(r.fingerprint)
                    return
        sys.exit(f"no provision {sys.argv[2]!r}")
    for s in lib.statuses:
        mark = "USABLE    " if s.usable else "NOT USABLE"
        print(f"{mark}  {s.pack.id}  {s.rule.id}  {s.rule.title}")
        for problem in s.problems:
            print(f"            - {problem}")
    print(f"\n{len(lib.usable_rules)} of {len(lib.statuses)} rules usable; versions {json.dumps(lib.versions())}")


if __name__ == "__main__":
    _cli()
