"""Evaluate a rule condition in Python, with the same semantics as policy/triage.rego.

Triage decisions always come from the Rego evaluator (WF-05). This copy decides only
which intake questions are showing, which is presentation, not a legal conclusion.
tests/test_triage.py checks the two agree on every rule in the content library.
"""
from __future__ import annotations

from typing import Any

from .content import Condition

_MISSING = object()


def holds(c: Condition, facts: dict[str, Any]) -> bool:
    if c.fact is not None:
        value = facts.get(c.fact, _MISSING)
        if value is _MISSING:
            return False                       # a missing fact never matches
        if c.equals is not None:
            return value == c.equals and type(value) is type(c.equals)
        if c.in_ is not None:
            return any(value == v and type(value) is type(v) for v in c.in_)
        if c.contains is not None:
            return isinstance(value, list) and c.contains in value
        if c.at_least is not None:
            return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= c.at_least
        return False
    if c.all is not None:
        return all(holds(x, facts) for x in c.all)
    if c.any is not None:
        return any(holds(x, facts) for x in c.any)
    if c.not_ is not None:
        return not holds(c.not_, facts)
    return False
