"""Review and approval of assessments (PLT-30 to PLT-35, SOD-1, SOD-2, WF-16, WF-20, WF-22).

- An editor submits the assessment for review. It must be complete and consistent, and it must
  record whether the business will go ahead (§ 7152(a)(7)). What was submitted is fixed by a
  digest, and editing stops until it is returned.
- Reviewers then act in the order the routing plan sets: provisional approval, then the final
  approvals. Any reviewer in the plan can instead return it with a note (it becomes editable
  again, and the next submission is a new round) or reject it.
- Policy/authz.rego decides segregation of duties: no approving your own work (SOD-1) and one
  approval per person per round (SOD-2).
- At least one final approver must confirm they have authority to take part in deciding
  whether the processing goes ahead (§ 7152(a)(9)).
- The DPO records risk acceptances for risks still high after safeguards (WF-20).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import approval
from . import assessment as engine
from . import audit
from .assessments_api import current_state, load_assessment, method_of, template
from .auth import Principal, current_principal
from .db import tenant_tx
from .main import actor_for, audit_actor, load_tenant, require

router = APIRouter()


class SubmitIn(BaseModel):
    note: str | None = Field(None, max_length=2000)


class ReviewIn(BaseModel):
    decision: Literal["approve", "return", "reject"]
    note: str | None = Field(None, max_length=4000)
    has_initiation_authority: bool = False
    self_approval_reason: str | None = Field(None, max_length=2000)


class AcceptanceIn(BaseModel):
    risk: str = Field(pattern=r"^r[0-9]{1,3}$")
    reason: str = Field(min_length=10, max_length=4000)
    review_date: date


def positions_of(conn, a: dict) -> dict[str, dict[str, Any]]:
    ids = [v["version_id"] for v in a["policy_versions"]]
    if not ids:
        return {}
    rows = conn.execute("""SELECT position_key, parameters FROM policy_position
                           WHERE policy_version_id = ANY(%s::uuid[])""", (ids,)).fetchall()
    return {r["position_key"]: r for r in rows}


def involved(conn, a: dict) -> list[str]:
    """SOD-1: everyone who opened, drafted (or asked the agent to draft), edited or submitted it."""
    who = {str(a["created_by"])}
    if a.get("submitted_by"):
        who.add(str(a["submitted_by"]))
    for r in conn.execute("""SELECT DISTINCT author_type, author_id, on_behalf_of FROM assessment_revision
                             WHERE assessment_id = %s""", (a["id"],)).fetchall():
        who.add(str(r["on_behalf_of"]) if r["author_type"] == "agent" else r["author_id"])
    return sorted(who)


def state_digest(state: dict[str, Any]) -> str:
    bodies = {sid: r["body"] for sid, r in state.items()}
    return hashlib.sha256(json.dumps(bodies, sort_keys=True).encode("utf-8")).hexdigest()


def decisions(conn, assessment_id: UUID, review_round: int | None = None) -> list[dict[str, Any]]:
    return conn.execute(
        """SELECT d.review_round, d.step, d.role, d.decision, d.note, d.has_initiation_authority,
                  d.self_approval_reason, d.decided_at, d.user_id, u.display_name AS name, u.job_title AS position
           FROM assessment_approval d JOIN app_user u ON u.id = d.user_id
           WHERE d.assessment_id = %s AND (%s::int IS NULL OR d.review_round = %s)
           ORDER BY d.decided_at, d.id""", (assessment_id, review_round, review_round)).fetchall()


def plan_for(conn, a: dict, tenant: dict) -> approval.Plan | None:
    if not a["routing_level"]:
        return None
    return approval.plan(a["routing_level"], tenant["approval_preset"], positions_of(conn, a))


def review_view(conn, a: dict, tenant: dict, p: Principal) -> dict[str, Any]:
    """Where review stands, for the assessment page."""
    plan = plan_for(conn, a, tenant)
    this_round = decisions(conn, a["id"], a["review_round"]) if a["review_round"] else []
    prog = approval.progress(plan, this_round) if plan and a["status"] == "in_review" else None
    roles = set(actor_for(p, tenant)["roles"])
    me = str(p.user_id)
    can_act = bool(prog and not prog["done"] and roles & set(prog["roles"]) and me not in involved(conn, a)
                   and me not in {str(d["user_id"]) for d in this_round if d["decision"] == "approve"})
    return {"status": a["status"], "round": a["review_round"], "routing_level": a["routing_level"],
            "plan": plan.__dict__ if plan else None, "next": prog, "can_act": can_act,
            "submitted_at": a["submitted_at"], "approved_at": a["approved_at"],
            "next_review_due": a["next_review_due"], "decisions": decisions(conn, a["id"])}


def approval_section(conn, a: dict) -> dict[str, Any] | None:
    """Section 9, filled in by the approval steps (§ 7152(a)(9)); legal counsel is listed
    internally but flagged, since the report itself leaves out counsel who gave legal advice."""
    if a["status"] != "approved":
        return None
    final = [d for d in decisions(conn, a["id"], a["review_round"]) if d["decision"] == "approve"]
    return {"approved_on": a["approved_at"].date().isoformat(), "reviewers": [
        {"name": d["name"], "position": d["position"] or "Not recorded", "role": d["role"], "step": d["step"],
         "date": d["decided_at"].date().isoformat(), "has_initiation_authority": d["has_initiation_authority"],
         "legal_counsel": d["role"] == "privacy_counsel", "self_approval_reason": d["self_approval_reason"]}
        for d in final]}


@router.post("/api/tenants/{tenant_id}/assessments/{assessment_id}/submit")
def submit(tenant_id: UUID, assessment_id: UUID, body: SubmitIn, p: Principal = Depends(current_principal)) -> dict:
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "assessment.submit", log_denial=True)
    tpl = template()
    with tenant_tx(tenant_id) as conn:
        a = conn.execute("SELECT * FROM assessment WHERE id = %s FOR UPDATE", (assessment_id,)).fetchone()
        if a is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "assessment not found")
        if a["status"] not in ("draft", "returned"):
            raise HTTPException(status.HTTP_409_CONFLICT, f"this assessment is {a['status']}")
        state = current_state(conn, assessment_id)
        bodies = {sid: r["body"] for sid, r in state.items()}
        computed = engine.derive(bodies, tpl, method_of(a), a["routing_floor"], a["risk_acceptances"])
        problems = list(computed["consistency_problems"])
        problems += [f"{tpl.section(s).title} has not been started" for s in computed["sections_not_started"]]
        if (bodies.get("decision") or {}).get("initiate", "undecided") == "undecided":
            problems.append("record whether the business will go ahead with the processing (section 7)")
        if problems:
            raise HTTPException(422, {"problems": problems})
        level = computed["routing"]["level"]
        digest = state_digest(state)
        conn.execute("""UPDATE assessment SET status = 'in_review', review_round = review_round + 1,
                               routing_level = %s, submitted_by = %s, submitted_at = now(), submitted_digest = %s,
                               updated_at = now() WHERE id = %s""", (level, p.user_id, digest, assessment_id))
        plan = approval.plan(level, tenant["approval_preset"], positions_of(conn, a))
        audit.append(conn, tenant_id, audit_actor(actor), "assessment.submitted", object_type="assessment",
                     object_id=str(assessment_id),
                     payload={"round": a["review_round"] + 1, "routing_level": level, "digest": digest,
                              "routing_source": plan.source, "note": body.note})
    return {"status": "in_review", "round": a["review_round"] + 1, "routing_level": level, "plan": plan.__dict__}


@router.post("/api/tenants/{tenant_id}/assessments/{assessment_id}/review")
def review(tenant_id: UUID, assessment_id: UUID, body: ReviewIn, p: Principal = Depends(current_principal)) -> dict:
    tenant = load_tenant(p, tenant_id)
    if body.decision != "approve" and not (body.note and body.note.strip()):
        raise HTTPException(422, "returning or rejecting needs a note saying why")
    with tenant_tx(tenant_id) as conn:
        a = conn.execute("SELECT * FROM assessment WHERE id = %s FOR UPDATE", (assessment_id,)).fetchone()
        if a is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "assessment not found")
        if a["status"] != "in_review":
            raise HTTPException(status.HTTP_409_CONFLICT, f"this assessment is {a['status']}, not in review")
        this_round = decisions(conn, assessment_id, a["review_round"])
        resource = {"involved": involved(conn, a),
                    "approved_this_round": [str(d["user_id"]) for d in this_round if d["decision"] == "approve"],
                    "self_approval_reason": body.self_approval_reason or ""}
    actor = require(p, tenant, "assessment.approve", resource, log_denial=True)
    with tenant_tx(tenant_id) as conn:
        a = conn.execute("SELECT * FROM assessment WHERE id = %s FOR UPDATE", (assessment_id,)).fetchone()
        if a["status"] != "in_review":
            raise HTTPException(status.HTTP_409_CONFLICT, f"this assessment is {a['status']}, not in review")
        this_round = decisions(conn, assessment_id, a["review_round"])
        plan = plan_for(conn, a, tenant)
        prog = approval.progress(plan, this_round)
        mine = set(actor["roles"])
        if body.decision == "approve":
            role = next((r for r in prog["roles"] if r in mine), None)
            if role is None:
                raise HTTPException(status.HTTP_403_FORBIDDEN,
                                    {"reasons": [f"the next approval needs one of: {', '.join(prog['roles'])}"]})
            step = prog["step"]
            after = approval.progress(plan, this_round + [{"decision": "approve", "step": step, "role": role}])
            attested = any(d["has_initiation_authority"] for d in this_round if d["step"] == "final")
            if after["done"] and not (attested or body.has_initiation_authority):
                raise HTTPException(422, {"problems": [
                    "at least one final approver must confirm they have authority to take part in deciding "
                    "whether the business goes ahead with this processing (CCPA Regulations § 7152(a)(9))"]})
        else:
            everyone = set(plan.provisional) | set(plan.final)
            role = next((r for r in plan.provisional + plan.final if r in mine), None)
            if not (mine & everyone):
                raise HTTPException(status.HTTP_403_FORBIDDEN, {"reasons": ["you are not a reviewer for this assessment"]})
            step = prog["step"] or "final"
        if a["submitted_digest"] != state_digest(current_state(conn, assessment_id)):
            raise HTTPException(status.HTTP_409_CONFLICT, "the assessment changed after it was submitted")
        conn.execute(
            """INSERT INTO assessment_approval (tenant_id, assessment_id, review_round, step, role, user_id, decision,
                                                note, has_initiation_authority, self_approval_reason, submitted_digest)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (tenant_id, assessment_id, a["review_round"], step, role, p.user_id, body.decision, body.note,
             body.has_initiation_authority and body.decision == "approve", body.self_approval_reason,
             a["submitted_digest"]))
        payload = {"round": a["review_round"], "step": step, "role": role, "note": body.note,
                   "has_initiation_authority": body.has_initiation_authority, "digest": a["submitted_digest"]}
        if body.self_approval_reason:
            payload["self_approval"] = body.self_approval_reason          # PLT-34: visible in the audit log
        audit.append(conn, tenant_id, audit_actor(actor), f"assessment.review_{body.decision}",
                     object_type="assessment", object_id=str(assessment_id), payload=payload)
        new_status = "in_review"
        if body.decision == "return":
            new_status = "returned"
        elif body.decision == "reject":
            new_status = "rejected"
        elif after["done"]:
            new_status = "approved"
        if new_status == "approved":
            bodies = {sid: r["body"] for sid, r in current_state(conn, assessment_id).items()}
            overall = engine.derive(bodies, template(), method_of(a), a["routing_floor"],
                                    a["risk_acceptances"])["overall_inherent"]
            today = datetime.now(timezone.utc).date()
            due = approval.next_review(today, overall, positions_of(conn, a))
            conn.execute("""UPDATE assessment SET status = 'approved', approved_at = now(), next_review_due = %s,
                            updated_at = now() WHERE id = %s""", (due, assessment_id))
            audit.append(conn, tenant_id, audit_actor(actor), "assessment.approved", object_type="assessment",
                         object_id=str(assessment_id),
                         payload={"round": a["review_round"], "digest": a["submitted_digest"],
                                  "next_review_due": due.isoformat()})
        elif new_status != "in_review":
            conn.execute("UPDATE assessment SET status = %s, updated_at = now() WHERE id = %s",
                         (new_status, assessment_id))
    return {"status": new_status, "step": step, "role": role}


@router.post("/api/tenants/{tenant_id}/assessments/{assessment_id}/risk-acceptances")
def accept_risk(tenant_id: UUID, assessment_id: UUID, body: AcceptanceIn,
                p: Principal = Depends(current_principal)) -> dict:
    """WF-20: the DPO accepts a risk that is still high after safeguards, with a reason and a
    review date. It is shown in the report and the audit trail."""
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "assessment.accept_risk", log_denial=True)
    if body.review_date <= datetime.now(timezone.utc).date():
        raise HTTPException(422, "the review date must be in the future")
    with tenant_tx(tenant_id) as conn:
        a = conn.execute("SELECT * FROM assessment WHERE id = %s FOR UPDATE", (assessment_id,)).fetchone()
        if a is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "assessment not found")
        if a["status"] not in ("draft", "returned"):
            raise HTTPException(status.HTTP_409_CONFLICT, "risks are accepted before the assessment goes to review")
        method = method_of(a)
        risks = (current_state(conn, assessment_id).get("risks") or {}).get("body", {}).get("risks", [])
        r = next((x for x in risks if x["id"] == body.risk), None)
        if r is None or not r.get("residual_likelihood"):
            raise HTTPException(422, f"{body.risk} is not a risk rated with safeguards in this assessment")
        residual = method.rate(r["residual_likelihood"], r["residual_severity"])
        if engine.LEVELS.index(residual) < engine.LEVELS.index(method.acceptance_needed_at):
            raise HTTPException(422, f"{body.risk} is {residual.replace('_', ' ')} after safeguards; "
                                     "no acceptance is needed")
        if any(x["risk"] == body.risk for x in a["risk_acceptances"]):
            raise HTTPException(status.HTTP_409_CONFLICT, f"{body.risk} already has a risk acceptance")
        name = conn.execute("SELECT display_name, job_title FROM app_user WHERE id = %s", (p.user_id,)).fetchone()
        rec = {"risk": body.risk, "risk_title": r["title"], "residual": residual, "reason": body.reason,
               "review_date": body.review_date.isoformat(), "by": str(p.user_id), "by_name": name["display_name"],
               "by_position": name["job_title"], "at": datetime.now(timezone.utc).isoformat()}
        conn.execute("""UPDATE assessment SET risk_acceptances = risk_acceptances || %s::jsonb, updated_at = now()
                        WHERE id = %s""", (Jsonb([rec]), assessment_id))
        audit.append(conn, tenant_id, audit_actor(actor), "assessment.risk_accepted", object_type="assessment",
                     object_id=str(assessment_id), payload=rec)
    return rec


__all__ = ["router", "review_view", "approval_section", "load_assessment"]
