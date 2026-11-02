"""The signed-in person's tasks: work that is waiting on them, for the Overview page.

Each group uses the same checks as the page where the work is done, so a task only shows when
that person can actually do it there: the policy engine's answer for the action, and for
approvals the same segregation-of-duties test as the Review and approval panel.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends

from .auth import Principal, current_principal
from .authz import decide
from .db import tenant_tx
from .main import actor_for, load_tenant
from .review_api import review_view

router = APIRouter()

# Shown in this order. Approvals first: they hold up everyone else.
GROUPS = [
    ("approve", "Risk assessments awaiting your approval"),
    ("returned", "Risk assessments returned for changes"),
    ("triage", "Triage results to confirm"),
    ("start", "Risk assessments to start"),
    ("in_progress", "Risk assessments in progress"),
    ("clarify", "Questions from the privacy office"),
    ("intake", "Intakes to finish"),
]


@router.get("/api/tenants/{tenant_id}/tasks")
def my_tasks(tenant_id: UUID, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    tenant = load_tenant(p, tenant_id)
    actor = actor_for(p, tenant)
    ctx = {"approval_preset": tenant["approval_preset"]}
    answers: dict[str, bool] = {}

    def allowed(action: str) -> bool:          # one policy-engine call per action, not per row
        if action not in answers:
            answers[action] = decide(actor, action, None, ctx).allow
        return answers[action]

    me = str(p.user_id)
    items: dict[str, list[dict[str, Any]]] = {k: [] for k, _ in GROUPS}

    def item(group: str, project: dict, assessment_id: Any = None, detail: str | None = None, since: Any = None):
        items[group].append({"project_id": str(project["project_id"]), "project_name": project["project_name"],
                             "assessment_id": str(assessment_id) if assessment_id else None,
                             "detail": detail, "since": since})

    with tenant_tx(tenant_id) as conn:
        if allowed("assessment.read"):
            rows = conn.execute(
                """SELECT a.*, pr.name AS project_name FROM assessment a JOIN project pr ON pr.id = a.project_id
                   WHERE a.status IN ('in_review', 'returned', 'draft') ORDER BY a.updated_at""").fetchall()
            for a in rows:
                if a["status"] == "in_review":
                    if review_view(conn, a, tenant, p)["can_act"]:
                        level = (a["routing_level"] or "").capitalize()
                        item("approve", a, a["id"], f"{level} risk, submitted" if level else "Submitted",
                             a["submitted_at"])
                elif allowed("draft.edit"):
                    if a["status"] == "returned":
                        note = conn.execute(
                            """SELECT d.note, u.display_name FROM assessment_approval d
                               JOIN app_user u ON u.id = d.user_id
                               WHERE d.assessment_id = %s AND d.decision = 'return'
                               ORDER BY d.decided_at DESC LIMIT 1""", (a["id"],)).fetchone()
                        item("returned", a, a["id"],
                             f"{note['display_name']}: {note['note']}" if note else None, a["updated_at"])
                    else:
                        item("in_progress", a, a["id"], "Draft", a["updated_at"])

        projects = conn.execute(
            """SELECT pr.id AS project_id, pr.name AS project_name, pr.status, pr.created_by, pr.clarification,
                      pr.updated_at,
                      (SELECT t.result FROM triage_run t WHERE t.project_id = pr.id AND t.status = 'confirmed'
                       ORDER BY t.created_at DESC LIMIT 1) AS confirmed_result,
                      EXISTS (SELECT 1 FROM assessment a WHERE a.project_id = pr.id) AS has_assessment
               FROM project pr ORDER BY pr.updated_at""").fetchall()
        for pr in projects:
            mine = str(pr["created_by"]) == me
            if pr["status"] == "triaged" and allowed("triage.confirm"):
                item("triage", pr, detail="The rules have run; an analyst confirms or changes the result",
                     since=pr["updated_at"])
            elif pr["status"] == "awaiting_clarification" and mine:
                item("clarify", pr, detail=pr["clarification"], since=pr["updated_at"])
            elif pr["status"] == "draft" and mine:
                item("intake", pr, detail="Not submitted yet", since=pr["updated_at"])
            elif (pr["status"] == "confirmed" and not pr["has_assessment"] and allowed("draft.edit")
                  and (pr["confirmed_result"] or {}).get("assessments")):
                item("start", pr, detail="Triage calls for a risk assessment", since=pr["updated_at"])

    groups = [{"id": k, "title": t, "items": items[k]} for k, t in GROUPS if items[k]]
    return {"groups": groups, "count": sum(len(g["items"]) for g in groups)}
