"""Authorization: every decision comes from Open Policy Agent (policy/authz.rego).

The API never decides on its own whether a role may act. If the policy
engine cannot be reached, the answer is no.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .config import settings


@dataclass
class Decision:
    allow: bool
    reasons: list[str]


def decide(actor: dict[str, Any], action: str, resource: dict[str, Any] | None = None,
           tenant: dict[str, Any] | None = None) -> Decision:
    payload = {"input": {"actor": actor, "action": action,
                         "resource": resource or {}, "tenant": tenant or {}}}
    try:
        r = httpx.post(f"{settings.opa_url}/v1/data/opendpo/authz/decision", json=payload, timeout=3)
        r.raise_for_status()
        result = r.json().get("result") or {}
    except httpx.HTTPError:
        return Decision(False, ["policy engine unavailable, so access is denied"])
    return Decision(bool(result.get("allow")), sorted(result.get("reasons", [])))
