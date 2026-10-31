"""Inventory and policy endpoints (INV-01 to INV-06, INV-09, PLT-12, PLT-13).

Read-only for the preview: the Harbor inventory and its policy copies are seeded. The
helpers here also give the agent the facts and policy positions an assessment draws on.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from . import policies
from .auth import Principal, current_principal
from .db import tenant_tx
from .main import load_tenant, require

router = APIRouter()


def activity_record(conn, activity_id: UUID) -> dict[str, Any] | None:
    """One processing activity with everything linked to it, as the assessment needs it."""
    act = conn.execute("SELECT * FROM processing_activity WHERE id = %s", (activity_id,)).fetchone()
    if act is None:
        return None
    act["systems"] = conn.execute(
        """SELECT s.*, v.name AS vendor_name FROM activity_system l JOIN system s ON s.id = l.system_id
           LEFT JOIN vendor v ON v.id = s.vendor_id WHERE l.activity_id = %s ORDER BY s.name""",
        (activity_id,)).fetchall()
    act["ai_components"] = conn.execute(
        """SELECT a.*, v.name AS vendor_name FROM activity_ai_component l JOIN ai_component a ON a.id = l.ai_component_id
           LEFT JOIN vendor v ON v.id = a.vendor_id WHERE l.activity_id = %s ORDER BY a.name""",
        (activity_id,)).fetchall()
    act["data_categories"] = conn.execute(
        """SELECT d.*, l.why_needed FROM activity_data_category l JOIN data_category d ON d.id = l.data_category_id
           WHERE l.activity_id = %s ORDER BY d.name""", (activity_id,)).fetchall()
    act["subject_groups"] = conn.execute(
        """SELECT g.* FROM activity_subject_group l JOIN data_subject_group g ON g.id = l.group_id
           WHERE l.activity_id = %s ORDER BY g.name""", (activity_id,)).fetchall()
    act["recipients"] = conn.execute(
        """SELECT v.*, l.purpose FROM activity_recipient l JOIN vendor v ON v.id = l.vendor_id
           WHERE l.activity_id = %s ORDER BY v.name""", (activity_id,)).fetchall()
    return act


def current_policies(conn) -> list[dict[str, Any]]:
    """Each policy's newest confirmed version, with its positions (PLT-13)."""
    versions = conn.execute(
        """SELECT DISTINCT ON (p.id) p.id AS policy_id, p.template_id, p.title, v.id AS version_id, v.version,
                  v.template_version, v.sections, v.status, v.effective_from, v.confirmed_at,
                  cu.display_name AS confirmed_by_name, pu.display_name AS proposed_by_name
           FROM policy p JOIN policy_version v ON v.policy_id = p.id
           LEFT JOIN app_user cu ON cu.id = v.confirmed_by LEFT JOIN app_user pu ON pu.id = v.proposed_by
           WHERE v.status = 'confirmed' ORDER BY p.id, v.version DESC""").fetchall()
    for v in versions:
        v["positions"] = conn.execute(
            """SELECT position_key, section, type, statement, applies_to, parameters, framework_refs
               FROM policy_position WHERE policy_version_id = %s ORDER BY position_key""",
            (v["version_id"],)).fetchall()
    return sorted(versions, key=lambda v: v["title"])


@router.get("/api/tenants/{tenant_id}/inventory/activities")
def list_activities(tenant_id: UUID, p: Principal = Depends(current_principal)) -> list[dict[str, Any]]:
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "inventory.read")
    with tenant_tx(tenant_id) as conn:
        return conn.execute("""SELECT id, name, decision_domain, ai_role, human_review, stage, go_live
                               FROM processing_activity ORDER BY name""").fetchall()


@router.get("/api/tenants/{tenant_id}/inventory/activities/{activity_id}")
def activity_detail(tenant_id: UUID, activity_id: UUID, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "inventory.read")
    with tenant_tx(tenant_id) as conn:
        act = activity_record(conn, activity_id)
    if act is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "processing activity not found")
    return act


@router.get("/api/tenants/{tenant_id}/policies")
def tenant_policies(tenant_id: UUID, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "policy.read")
    reviews = {s.template.id: {"version": s.template.version, "reviewed": s.reviewed, "problems": s.problems}
               for s in policies.load()}
    with tenant_tx(tenant_id) as conn:
        current = current_policies(conn)
    for v in current:
        v["template_review"] = reviews.get(v["template_id"])
    return {"policies": current}
