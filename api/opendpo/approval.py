"""Who must approve an assessment, in what order (PLT-09, PLT-30, PLT-35, SOD-2).

Routing comes from the tenant's own policy: the approval_rule position POS-RA-004 in the
policy versions the assessment recorded. If no such position exists, the standard preset in
the requirements applies. The tenant's approval preset then shapes it:

- standard: as the policy says (high risk: analyst provisional approval, then the DPO and
  privacy counsel, two different people);
- lean and single_person: one final approver at every level, no provisional step.

Segregation of duties (SOD-1, SOD-2) is decided by policy/authz.rego, not here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

DEFAULT_ROUTING = {
    "low": {"provisional": [], "final": ["privacy_analyst"]},
    "medium": {"provisional": ["privacy_analyst"], "final": ["privacy_counsel"]},
    "high": {"provisional": ["privacy_analyst"], "final": ["dpo", "privacy_counsel"], "distinct_people": True},
}
DEFAULT_REVIEW_YEARS = {"very_high": 1, "high": 1, "moderate": 2, "low": 3, "very_low": 3}
ROUTING_POSITION = "POS-RA-004"
REVIEW_POSITION = "POS-RA-008"


@dataclass
class Plan:
    level: str
    preset: str
    provisional: list[str]          # roles; any one of them gives the provisional approval
    final: list[str]                # roles that must each approve (standard), or any one (lean)
    each_final_role: bool
    source: str                     # where the routing came from


def plan(level: str, preset: str, positions: dict[str, dict[str, Any]]) -> Plan:
    pos = positions.get(ROUTING_POSITION)
    table = (pos or {}).get("parameters", {}).get("routing") or DEFAULT_ROUTING
    route = table[level]
    source = f"{ROUTING_POSITION} in the organization's policy" if pos else "OpenDPO's standard preset"
    if preset == "standard":
        return Plan(level, preset, list(route.get("provisional", [])), list(route["final"]), True, source)
    return Plan(level, preset, [], list(route["final"]), False, source)


def progress(p: Plan, decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Where review stands for one round: what is done and what comes next."""
    approvals = [d for d in decisions if d["decision"] == "approve"]
    provisional = [d for d in approvals if d["step"] == "provisional"]
    finals = [d for d in approvals if d["step"] == "final"]
    if p.provisional and not provisional:
        return {"step": "provisional", "roles": p.provisional, "done": False}
    if p.each_final_role:
        pending = [r for r in p.final if r not in {d["role"] for d in finals}]
    else:
        pending = [] if finals else p.final
    if pending:
        return {"step": "final", "roles": pending, "done": False}
    return {"step": None, "roles": [], "done": True}


def review_years(positions: dict[str, dict[str, Any]]) -> dict[str, int]:
    pos = positions.get(REVIEW_POSITION)
    return (pos or {}).get("parameters", {}).get("review_years") or DEFAULT_REVIEW_YEARS


def next_review(approved_on: date, overall: str | None, positions: dict[str, dict[str, Any]]) -> date:
    """WF-22: the scheduled re-review, by the highest inherent risk."""
    years = review_years(positions).get(overall or "low", 3)
    try:
        return approved_on.replace(year=approved_on.year + years)
    except ValueError:                       # 29 February
        return approved_on.replace(year=approved_on.year + years, day=28)
