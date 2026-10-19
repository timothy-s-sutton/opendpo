"""Tamper-evident audit log (PLT-40, PLT-41, PLT-42).

Each tenant has its own chain. Every event stores the SHA-256 hash of the
previous event, and its own hash covers its content plus that link, so any
edit, deletion or reordering breaks the chain at that point.

Verify from the command line:
    python -m opendpo.audit verify --tenant <tenant id>
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import psycopg

GENESIS = "0" * 64


@dataclass(frozen=True)
class Actor:
    type: str                      # "user", "agent" or "system"
    id: str
    roles: tuple[str, ...] = ()
    on_behalf_of: str | None = None  # SOD-6: who triggered an agent action


def canonical(event: dict[str, Any]) -> str:
    """The exact text that is hashed. Stable across reads and Python versions."""
    body = {
        "tenant_id": str(event["tenant_id"]),
        "seq": event["seq"],
        "occurred_at": _ts(event["occurred_at"]),
        "actor_type": event["actor_type"],
        "actor_id": event["actor_id"],
        "actor_roles": sorted(event["actor_roles"] or []),
        "on_behalf_of": event["on_behalf_of"],
        "action": event["action"],
        "object_type": event["object_type"],
        "object_id": event["object_id"],
        "payload": event["payload"] or {},
        "content_versions": event["content_versions"] or {},
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def link_hash(prev_hash: str, event: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + "\n" + canonical(event)).encode("utf-8")).hexdigest()


def append(conn: psycopg.Connection, tenant_id: UUID, actor: Actor, action: str, *,
           object_type: str | None = None, object_id: str | None = None,
           payload: dict[str, Any] | None = None,
           content_versions: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append one event to the tenant's chain, inside the caller's transaction."""
    # Serialize writers per tenant so two events never claim the same link.
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"audit:{tenant_id}",))
    last = conn.execute(
        "SELECT seq, hash FROM audit_event WHERE tenant_id = %s ORDER BY seq DESC LIMIT 1",
        (tenant_id,)).fetchone()
    seq = (last["seq"] + 1) if last else 1
    prev = last["hash"] if last else GENESIS
    event = {
        "tenant_id": tenant_id, "seq": seq,
        "occurred_at": datetime.now(timezone.utc),
        "actor_type": actor.type, "actor_id": actor.id, "actor_roles": sorted(actor.roles),
        "on_behalf_of": actor.on_behalf_of, "action": action,
        "object_type": object_type, "object_id": object_id,
        "payload": payload or {}, "content_versions": content_versions or {},
    }
    event["prev_hash"] = prev
    event["hash"] = link_hash(prev, event)
    conn.execute(
        """INSERT INTO audit_event (tenant_id, seq, occurred_at, actor_type, actor_id, actor_roles,
               on_behalf_of, action, object_type, object_id, payload, content_versions,
               prev_hash, hash)
           VALUES (%(tenant_id)s, %(seq)s, %(occurred_at)s, %(actor_type)s, %(actor_id)s,
               %(actor_roles)s, %(on_behalf_of)s, %(action)s, %(object_type)s, %(object_id)s,
               %(payload)s, %(content_versions)s, %(prev_hash)s, %(hash)s)""",
        {**event, "payload": psycopg.types.json.Jsonb(event["payload"]),
         "content_versions": psycopg.types.json.Jsonb(event["content_versions"])})
    return event


@dataclass
class VerifyResult:
    ok: bool
    events_checked: int
    first_broken_seq: int | None = None
    problem: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "events_checked": self.events_checked,
                "first_broken_seq": self.first_broken_seq, "problem": self.problem}


def verify(conn: psycopg.Connection, tenant_id: UUID) -> VerifyResult:
    """Walk the chain in order and report the first broken link."""
    rows = conn.execute(
        "SELECT * FROM audit_event WHERE tenant_id = %s ORDER BY seq", (tenant_id,))
    prev = GENESIS
    expected_seq = 1
    count = 0
    for row in rows:
        count += 1
        if row["seq"] != expected_seq:
            return VerifyResult(False, count, expected_seq, "event missing from the sequence")
        if row["prev_hash"] != prev:
            return VerifyResult(False, count, row["seq"], "link to the previous event does not match")
        if link_hash(prev, row) != row["hash"]:
            return VerifyResult(False, count, row["seq"], "event content changed after it was written")
        prev = row["hash"]
        expected_seq += 1
    return VerifyResult(True, count)


def _cli() -> None:
    import argparse
    import sys

    from psycopg.rows import dict_row

    from .config import settings

    parser = argparse.ArgumentParser(prog="python -m opendpo.audit")
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="verify a tenant's audit chain")
    v.add_argument("--tenant", required=True, type=UUID)
    args = parser.parse_args()
    with psycopg.connect(settings.app_dsn, row_factory=dict_row) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(args.tenant),))
        result = verify(conn, args.tenant)
    if result.ok:
        print(f"OK: {result.events_checked} events, chain intact")
    else:
        print(f"BROKEN at event {result.first_broken_seq}: {result.problem}")
        sys.exit(1)


if __name__ == "__main__":
    _cli()
