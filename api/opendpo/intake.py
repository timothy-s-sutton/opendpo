"""The project intake form (WF-01, WF-02, WF-04).

content/intake.yaml places questions: core questions defined there, and pack facts
named by id. This module turns that layout into a JSON Schema the web app renders,
decides which questions are showing for a given set of answers, and validates a
submission against exactly the questions that were showing.

Each pack question carries its governing definitions (the fact's defined_by), so the
form can show the law's own words beside the question.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict

from . import content
from .conditions import holds

INTAKE_FILE = Path(os.environ.get("OPENDPO_INTAKE_FILE", content.CONTENT_DIR.parent / "intake.yaml"))

AI_QUESTION = "project.uses_ai"
NOT_SURE = "not_sure"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CoreOption(_Strict):
    value: str
    label: str
    sensitive: bool = False


class CoreQuestion(_Strict):
    id: str
    question: str
    type: Literal["text", "textarea", "date", "boolean", "choice", "multichoice"]
    options: list[CoreOption] | None = None
    help: str | None = None
    placeholder: str | None = None


class Placement(_Strict):
    fact: str
    show_when: content.Condition | None = None


class Section(_Strict):
    pack: str
    title: str
    show_when: content.Condition | None = None
    questions: list[Placement]


class Layout(_Strict):
    version: int
    core: list[CoreQuestion | Placement]
    sections: list[Section]


@dataclass
class Question:
    """One question as the form shows it, core or pack."""
    id: str
    question: str
    type: str
    section: str                       # "core" or a pack id
    options: list[dict] = field(default_factory=list)
    help: str | None = None
    placeholder: str | None = None
    show_when: list[content.Condition] = field(default_factory=list)   # all must hold
    pack: str | None = None
    definitions: list[dict] = field(default_factory=list)
    rules_usable: bool = True          # False when no usable rule tests this question yet


@dataclass
class Form:
    layout: Layout
    questions: list[Question]
    sections: list[dict]

    def by_id(self) -> dict[str, Question]:
        return {q.id: q for q in self.questions}

    def visible(self, answers: dict[str, Any]) -> list[Question]:
        """Questions showing for these answers. A question whose condition depends on a
        hidden question is hidden too, so answers are pruned in form order."""
        shown: list[Question] = []
        kept: dict[str, Any] = {}
        for q in self.questions:
            if all(holds(c, kept) for c in q.show_when):
                shown.append(q)
                if q.id in answers:
                    kept[q.id] = answers[q.id]
        return shown

    def prune(self, answers: dict[str, Any]) -> dict[str, Any]:
        """Only the answers to questions that are showing; the rest are not part of the intake."""
        ids = {q.id for q in self.visible(answers)}
        return {k: v for k, v in answers.items() if k in ids}

    def json_schema(self, only: list[Question] | None = None, required: bool = False) -> dict[str, Any]:
        qs = self.questions if only is None else only
        schema: dict[str, Any] = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://opendpo.dev/schemas/intake/v{self.layout.version}",
            "title": "OpenDPO project intake",
            "type": "object",
            "properties": {q.id: _property(q) for q in qs},
            "additionalProperties": False,
            "x-opendpo-sections": self.sections,
        }
        if required:
            schema["required"] = [q.id for q in qs]
        return schema

    def validate(self, answers: dict[str, Any]) -> list[dict[str, str]]:
        """Every showing question answered, every answer well formed. Returns problems."""
        shown = self.visible(answers)
        schema = self.json_schema(shown, required=True)
        problems = []
        for err in sorted(Draft202012Validator(schema).iter_errors(self.prune(answers)), key=lambda e: list(e.path)):
            where = ".".join(str(p) for p in err.path)
            if err.validator == "required":
                missing = err.message.split("'")[1]
                problems.append({"question": missing, "problem": "needs an answer"})
            else:
                problems.append({"question": where, "problem": err.message})
        return problems


def _property(q: Question) -> dict[str, Any]:
    meta = {"section": q.section, "type": q.type,
            "show_when": [c.model_dump(by_alias=True, exclude_none=True) for c in q.show_when]}
    if q.pack:
        meta.update(pack=q.pack, definitions=q.definitions, rules_usable=q.rules_usable)
    if q.placeholder:
        meta["placeholder"] = q.placeholder
    p: dict[str, Any] = {"title": q.question, "x-opendpo": meta}
    if q.help:
        p["description"] = q.help
    one_of = [{"const": o["value"], "title": o["label"]} for o in q.options]
    if q.type == "boolean":
        p["type"] = "boolean"
    elif q.type in ("text", "textarea"):
        p.update(type="string", minLength=1)
    elif q.type == "date":
        p.update(type="string", format="date", pattern=r"^\d{4}-\d{2}-\d{2}$")
    elif q.type == "number":
        p["type"] = "number"
    elif q.type == "choice":
        p["oneOf"] = one_of
    elif q.type == "multichoice":
        p.update(type="array", items={"oneOf": one_of}, uniqueItems=True)
        sensitive = [o["value"] for o in q.options if o.get("sensitive")]
        if sensitive:
            meta["sensitive_options"] = sensitive
    return p


def build(lib: content.Library, path: Path = INTAKE_FILE) -> Form:
    layout = Layout.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    facts: dict[str, tuple[content.Pack, content.Fact]] = {}
    for pack in lib.packs:
        for f in pack.facts:
            if f.id in facts:
                raise ValueError(f"fact {f.id} is declared in both {facts[f.id][0].id} and {pack.id}")
            facts[f.id] = (pack, f)
    provisions = lib.provision_index()
    tested = {fid for st in lib.statuses if st.usable for fid in st.rule.when.facts()}

    def pack_question(p: Placement, section: str, inherited: list[content.Condition]) -> Question:
        if p.fact not in facts:
            raise ValueError(f"intake places {p.fact!r}, which no pack declares")
        pack, f = facts[p.fact]
        if f.asked_in != "intake":
            raise ValueError(f"intake places {f.id}, which is asked in {f.asked_in}")
        defs = []
        for pid in f.defined_by:
            owner, prov = provisions[pid]
            src = next(s for s in owner.sources if s.id == prov.source)
            defs.append({"id": pid, "citation": prov.citation, "summary": prov.summary, "text": prov.text,
                         "source": src.title, "source_url": src.url, "location": prov.location,
                         "verified": content.provision_status(prov, lib.verifications[owner.id].get(pid)) is None})
        conds = inherited + ([p.show_when] if p.show_when else [])
        return Question(f.id, f.question, f.type, section, [o.model_dump() for o in f.options or []],
                        f.help, None, conds, pack.id, defs, f.id in tested)

    questions: list[Question] = []
    for item in layout.core:
        if isinstance(item, Placement):
            questions.append(pack_question(item, "core", []))
        else:
            questions.append(Question(item.id, item.question, item.type, "core",
                                      [o.model_dump() for o in item.options or []], item.help, item.placeholder))
    sections = [{"id": "core", "title": "About the project"}]
    for s in layout.sections:
        if s.pack not in {p.id for p in lib.packs}:
            raise ValueError(f"intake section names unknown pack {s.pack}")
        usable = [st for st in lib.statuses if st.pack.id == s.pack]
        sections.append({"id": s.pack, "title": s.title,
                         "show_when": s.show_when.model_dump(by_alias=True, exclude_none=True) if s.show_when else None,
                         "rules_usable": sum(st.usable for st in usable), "rules_total": len(usable)})
        for p in s.questions:
            questions.append(pack_question(p, s.pack, [s.show_when] if s.show_when else []))
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("intake places a question twice")
    # Every condition must refer to a question asked before it, so pruning in form order is sound.
    seen: set[str] = set()
    for q in questions:
        for c in q.show_when:
            later = c.facts() - seen
            if later:
                raise ValueError(f"{q.id} is shown based on {sorted(later)}, which come later or are not asked")
        seen.add(q.id)
    return Form(layout, questions, sections)


def unplaced(lib: content.Library, form: Form) -> list[str]:
    """Intake facts no section asks: rules that test them could never fire."""
    placed = {q.id for q in form.questions}
    return sorted(f.id for p in lib.packs for f in p.facts if f.asked_in == "intake" and f.id not in placed)
