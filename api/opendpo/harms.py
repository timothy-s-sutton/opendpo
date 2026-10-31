"""The unified harm list (WF-25), loaded as content behind the verification gate.

A harm is usable in an assessment only when:
- its quote appears word for word in the provision that names it,
- that provision and every related provision is verified and current, and
- Tim's sign-off record matches the entry's fingerprint (any edit lapses it).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from . import content

HARMS_DIR = content.CONTENT_DIR.parent / "harms"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Link(Strict):
    provision: str
    why: str = Field(min_length=3)


class Harm(Strict):
    id: str = Field(pattern=r"^harm-[a-z-]+$")
    name: str
    description: str
    named_by: str
    clause: str
    quote: str
    related: list[Link] = []
    framework_tags: list[str] = []

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode("utf-8")).hexdigest()


class HarmList(Strict):
    id: str
    version: str
    harms: list[Harm]


class SignOff(Strict):
    harm: str
    fingerprint: str
    verified_by: str
    verified_on: date
    method: str = "Checked the quote, the links and the plain-language wording against the verified provisions"
    self_verified: bool = True
    note: str | None = None


@dataclass
class HarmStatus:
    harm: Harm
    usable: bool
    problems: list[str] = field(default_factory=list)


@dataclass
class Harms:
    id: str
    version: str
    statuses: list[HarmStatus]

    def usable(self) -> dict[str, Harm]:
        return {s.harm.id: s.harm for s in self.statuses if s.usable}

    def by_id(self) -> dict[str, HarmStatus]:
        return {s.harm.id: s for s in self.statuses}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def load(lib: content.Library, tags: set[str], directory: Path = HARMS_DIR) -> Harms:
    data = HarmList.model_validate(yaml.safe_load((directory / "harms.yaml").read_text(encoding="utf-8")))
    vfile = directory / "verification.yaml"
    raw = (yaml.safe_load(vfile.read_text(encoding="utf-8")) or []) if vfile.is_file() else []
    records = {r.harm: r for r in (SignOff.model_validate(x) for x in raw)}
    ids = [h.id for h in data.harms]
    if len(ids) != len(set(ids)):
        raise ValueError("harms.yaml: each harm needs its own id")
    unknown = set(records) - set(ids)
    if unknown:
        raise ValueError(f"harms verification.yaml: records for unknown harms {sorted(unknown)}")
    index = lib.provision_index()
    statuses = []
    for h in data.harms:
        bad_tags = set(h.framework_tags) - tags
        if bad_tags:
            raise ValueError(f"{h.id}: unknown framework tags {sorted(bad_tags)}")
        problems = []
        for pid in [h.named_by] + [link.provision for link in h.related]:
            if pid not in index:
                raise ValueError(f"{h.id}: unknown provision {pid}")
            owner, prov = index[pid]
            issue = content.provision_status(prov, lib.verifications[owner.id].get(pid))
            if issue:
                problems.append(issue)
        if _norm(h.quote) not in _norm(index[h.named_by][1].text):
            problems.append(f"the quote does not appear word for word in {h.named_by}")
        rec = records.get(h.id)
        if rec is None:
            problems.append("not yet signed off")
        elif rec.fingerprint != h.fingerprint:
            problems.append(f"changed after it was signed off on {rec.verified_on}; sign it off again")
        statuses.append(HarmStatus(h, not problems, problems))
    return Harms(data.id, data.version, statuses)


def worksheet(lib: content.Library, harms: Harms) -> str:
    """The sign-off worksheet, in markdown, one tick box per harm."""
    index = lib.provision_index()
    out = ["## Harms: is each entry a fair, accurate reading of the law?", "",
           "Each harm is one of the example negative impacts in the CCPA Regulations, § 7152(a)(5). "
           "Software already checked that each quote appears word for word in the verified text of § 7152(a)(5). "
           "For each harm, check three things: the plain-language name and description say what the quote says; "
           "each related provision really bears on this harm, and the reason given is fair; and the NIST AI RMF "
           "tags fit (they are a framework reference, not law). Comment on anything you would change; "
           "I will update the entry and ask again.", ""]
    for s in harms.statuses:
        h = s.harm
        out += [f"### {h.name}", "", f"ID `{h.id}` · {index[h.named_by][1].citation}{h.clause}", "",
                f"> {_norm(h.quote)}", "", f"**Plain-language description:** {_norm(h.description)}", ""]
        if h.related:
            out.append("**Related provisions:**")
            for link in h.related:
                out.append(f"- {index[link.provision][1].citation}: {link.why}")
            out.append("")
        else:
            out += ["**Related provisions:** none yet", ""]
        out += [f"**NIST AI RMF tags:** {', '.join(h.framework_tags) or 'none'}", "",
                f"- [ ] Entry is accurate and the links are fair ({h.id})", ""]
    return "\n".join(out)


if __name__ == "__main__":
    import sys

    from .assessment import load_template

    lib = content.load()
    hs = load(lib, {t.id for t in load_template(lib).framework_tags})
    if sys.argv[1:2] == ["worksheet"]:
        print(worksheet(lib, hs))
    elif sys.argv[1:2] == ["fingerprint"]:
        for s in hs.statuses:
            print(s.harm.id, s.harm.fingerprint)
    else:
        for s in hs.statuses:
            print(("USABLE    " if s.usable else "NOT USABLE"), s.harm.id, "; ".join(s.problems))
