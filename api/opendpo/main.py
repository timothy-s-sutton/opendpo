"""OpenDPO API (foundation): identity, tenancy, authorization and the audit log."""
from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from . import audit
from .auth import Principal, current_principal
from .authz import decide
from .config import settings
from .db import global_tx, tenant_tx

NOTICE = ("OpenDPO is a proof of concept. It provides no legal advice and is not a "
          "substitute for review by qualified privacy, legal and compliance professionals.")

app = FastAPI(title="OpenDPO API", version="0.1.0", description=NOTICE)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                   allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

# Actions the web app asks about to decide what to show a user.
UI_ACTIONS = ["intake.submit", "triage.confirm", "draft.edit", "assessment.approve",
              "members.read", "tenant.ack_intended_use", "audit.read", "audit.verify", "audit.export"]


def actor_for(p: Principal, tenant: dict) -> dict[str, Any]:
    ws_roles = [w["role"] for w in p.workspace_roles if w["workspace_id"] == tenant["workspace_id"]]
    return {"type": "user", "id": str(p.user_id), "roles": p.tenant_roles(tenant["id"]),
            "workspace_roles": ws_roles}


def load_tenant(p: Principal, tenant_id: UUID) -> dict:
    """The tenant, if the principal belongs to it; otherwise a 404 that reveals nothing."""
    with tenant_tx(tenant_id) as conn:
        tenant = conn.execute("SELECT * FROM tenant WHERE id = %s", (tenant_id,)).fetchone()
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tenant not found")
    actor = actor_for(p, tenant)
    if not actor["roles"] and not actor["workspace_roles"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tenant not found")
    return tenant


def require(p: Principal, tenant: dict, action: str, resource: dict | None = None,
            log_denial: bool = False) -> dict[str, Any]:
    actor = actor_for(p, tenant)
    d = decide(actor, action, resource, {"approval_preset": tenant["approval_preset"]})
    if not d.allow:
        if log_denial:
            with tenant_tx(tenant["id"]) as conn:
                audit.append(conn, tenant["id"], audit.Actor("user", actor["id"], tuple(actor["roles"])),
                             "access.denied", payload={"attempted": action, "reasons": d.reasons,
                                                       "resource": resource or {}})
        raise HTTPException(status.HTTP_403_FORBIDDEN, {"action": action, "reasons": d.reasons})
    return actor


def audit_actor(actor: dict) -> audit.Actor:
    return audit.Actor("user", actor["id"], tuple(actor["roles"] + actor["workspace_roles"]))


@app.get("/api/health")
def health() -> dict[str, Any]:
    db_ok = opa_ok = False
    try:
        with global_tx() as conn:
            db_ok = conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
    except Exception:  # noqa: BLE001 - health reports, never raises
        pass
    try:
        opa_ok = httpx.get(f"{settings.opa_url}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        pass
    return {"status": "ok" if db_ok and opa_ok else "degraded", "database": db_ok,
            "policy_engine": opa_ok, "notice": NOTICE}


@app.get("/api/me")
def me(p: Principal = Depends(current_principal)) -> dict[str, Any]:
    tenants: dict[UUID, dict] = {}
    for m in p.memberships:
        t = tenants.setdefault(m["tenant_id"], {"id": m["tenant_id"], "name": m["tenant_name"], "roles": []})
        t["roles"].append(m["role"])
    return {"id": p.user_id, "username": p.username, "display_name": p.display_name,
            "tenants": list(tenants.values()),
            "workspace_roles": [{"workspace_id": w["workspace_id"], "role": w["role"]} for w in p.workspace_roles]}


@app.get("/api/tenants/{tenant_id}")
def tenant_detail(tenant_id: UUID, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    tenant = load_tenant(p, tenant_id)
    actor = actor_for(p, tenant)
    preset = {"approval_preset": tenant["approval_preset"]}
    allowed = [a for a in UI_ACTIONS if decide(actor, a, None, preset).allow]
    return {"id": tenant["id"], "name": tenant["name"], "approval_preset": tenant["approval_preset"],
            "intended_use_acknowledged": tenant["intended_use_ack_at"] is not None,
            "intended_use_ack_at": tenant["intended_use_ack_at"],
            "my_roles": actor["roles"], "my_workspace_roles": actor["workspace_roles"],
            "allowed_actions": allowed}


@app.post("/api/tenants/{tenant_id}/intended-use/ack")
def ack_intended_use(tenant_id: UUID, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """USE-04: an admin acknowledges the intended-use notice; the acknowledgment is audited."""
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "tenant.ack_intended_use", log_denial=True)
    with tenant_tx(tenant_id) as conn:
        row = conn.execute(
            """UPDATE tenant SET intended_use_ack_at = now(), intended_use_ack_by = %s
               WHERE id = %s AND intended_use_ack_at IS NULL RETURNING intended_use_ack_at""",
            (p.user_id, tenant_id)).fetchone()
        if row is None:
            return {"acknowledged": True, "already": True}
        audit.append(conn, tenant_id, audit_actor(actor), "tenant.intended_use_acknowledged",
                     object_type="tenant", object_id=str(tenant_id), payload={"notice": NOTICE})
    return {"acknowledged": True, "at": row["intended_use_ack_at"]}


@app.get("/api/tenants/{tenant_id}/members")
def members(tenant_id: UUID, p: Principal = Depends(current_principal)) -> list[dict[str, Any]]:
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "members.read")
    with tenant_tx(tenant_id) as conn:
        return conn.execute(
            """SELECT u.id, u.display_name, u.username, m.role FROM membership m
               JOIN app_user u ON u.id = m.user_id ORDER BY m.role, u.display_name""").fetchall()


@app.get("/api/tenants/{tenant_id}/audit")
def audit_events(tenant_id: UUID, limit: int = Query(100, ge=1, le=1000),
                 p: Principal = Depends(current_principal)) -> list[dict[str, Any]]:
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "audit.read")
    with tenant_tx(tenant_id) as conn:
        return conn.execute(
            """SELECT e.seq, e.occurred_at, e.actor_type, e.actor_id, coalesce(u.display_name, e.actor_id)
                      AS actor_name, e.actor_roles, e.on_behalf_of, e.action, e.object_type, e.object_id,
                      e.payload, e.prev_hash, e.hash
               FROM audit_event e LEFT JOIN app_user u ON u.id::text = e.actor_id
               ORDER BY e.seq DESC LIMIT %s""", (limit,)).fetchall()


@app.post("/api/tenants/{tenant_id}/audit/verify")
def audit_verify(tenant_id: UUID, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "audit.verify")
    with tenant_tx(tenant_id) as conn:
        result = audit.verify(conn, tenant_id)
        audit.append(conn, tenant_id, audit_actor(actor), "audit.verified", payload=result.as_dict())
    return result.as_dict()


@app.get("/api/tenants/{tenant_id}/audit/export")
def audit_export(tenant_id: UUID, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """PLT-42: JSON export. The chain is verified first (PLT-43) and the export itself is logged."""
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "audit.export", log_denial=True)
    with tenant_tx(tenant_id) as conn:
        result = audit.verify(conn, tenant_id)
        events = conn.execute("SELECT * FROM audit_event ORDER BY seq").fetchall()
        audit.append(conn, tenant_id, audit_actor(actor), "audit.exported",
                     payload={"events": len(events), "verification": result.as_dict()})
    for e in events:
        e.pop("id", None)
    return {"tenant": {"id": tenant["id"], "name": tenant["name"]}, "notice": NOTICE,
            "verification": result.as_dict(), "events": events}
