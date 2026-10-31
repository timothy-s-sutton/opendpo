"""OpenDPO policy templates (PLT-10 to PLT-19), loaded and checked as content.

A template is OpenDPO's own text with structured positions (PLT-12). Before it can seed a
tenant, Tim signs off its wording and positions; the record in review.yaml covers the whole
template by fingerprint, so any later change lapses it. Each tenant then holds its own
versioned copy in the database.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import content

POLICY_DIR = content.CONTENT_DIR.parent / "policies"
PositionType = Literal["requirement", "prohibition", "threshold", "approval_rule", "default",
                       "conditional_permission"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Section(Strict):
    number: str
    title: str
    text: str


class Position(Strict):
    id: str = Field(pattern=r"^POS-[A-Z]+-[0-9]{3}$")
    section: str
    type: PositionType
    statement: str
    applies_to: dict[str, Any] = {}
    parameters: dict[str, Any] = {}
    framework_refs: list[str] = []


class Template(Strict):
    id: str
    title: str
    version: str
    license: Literal["CC BY 4.0"]
    authored_by: str
    reused_sources: list[dict[str, str]] = []
    framework_anchors: list[str] = []
    sections: list[Section]
    positions: list[Position]

    @model_validator(mode="after")
    def positions_point_at_sections(self) -> "Template":
        ids = [p.id for p in self.positions]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.id}: each position needs its own id")
        numbers = {s.number for s in self.sections}
        for p in self.positions:
            if p.section.split(".")[0] not in numbers:
                raise ValueError(f"{self.id}: {p.id} points at missing section {p.section}")
        return self

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode("utf-8")).hexdigest()


class Review(Strict):
    template: str
    fingerprint: str
    reviewed_by: str
    reviewed_on: date
    note: str | None = None


@dataclass
class TemplateStatus:
    template: Template
    reviewed: bool
    problems: list[str] = field(default_factory=list)


def load(directory: Path = POLICY_DIR) -> list[TemplateStatus]:
    out = []
    for d in sorted(p for p in directory.iterdir() if (p / "policy.yaml").is_file()):
        t = Template.model_validate(yaml.safe_load((d / "policy.yaml").read_text(encoding="utf-8")))
        if t.id != d.name:
            raise ValueError(f"policy template id {t.id!r} must match its folder {d.name!r}")
        rfile = d / "review.yaml"
        rec = Review.model_validate(yaml.safe_load(rfile.read_text(encoding="utf-8"))) if rfile.is_file() else None
        problems = []
        if rec is None:
            problems.append("not yet reviewed")
        elif rec.fingerprint != t.fingerprint:
            problems.append(f"changed after it was reviewed on {rec.reviewed_on}; review it again")
        out.append(TemplateStatus(t, not problems, problems))
    return out


def worksheet(statuses: list[TemplateStatus]) -> str:
    out = []
    for s in statuses:
        t = s.template
        out += [f"## {t.title}", "", f"Template `{t.id}` version {t.version} · {t.license} · written by "
                f"{t.authored_by}, no reused text · anchors: {', '.join(t.framework_anchors)}", "",
                "### Policy text", ""]
        for sec in t.sections:
            out += [f"**{sec.number}. {sec.title}**", "", sec.text.replace("{organization}", "the organization").strip(), ""]
        out += ["### Positions", "", "Each position is one rule from the text above, stored as a record that "
                "assessments can cite. Check that each says what the text says and has the right type.", ""]
        for p in t.positions:
            params = json.dumps(p.parameters, sort_keys=True)
            out += [f"- **{p.id}** ({p.type}, section {p.section}): {' '.join(p.statement.split())}",
                    f"    - Parameters: `{params}`",
                    f"    - Framework references: {', '.join(p.framework_refs) or 'none'}"]
        out += ["", f"- [ ] Wording and positions are what my policy would say ({t.id})", ""]
    return "\n".join(out)


if __name__ == "__main__":
    import sys

    sts = load()
    if sys.argv[1:2] == ["worksheet"]:
        print(worksheet(sts))
    elif sys.argv[1:2] == ["fingerprint"]:
        for s in sts:
            print(s.template.id, s.template.fingerprint)
    else:
        for s in sts:
            print(("REVIEWED    " if s.reviewed else "NOT REVIEWED"), s.template.id, "; ".join(s.problems))
