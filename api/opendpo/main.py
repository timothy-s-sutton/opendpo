"""OpenDPO API: identity, tenancy, authorization, the audit log, intake, triage and assessments."""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import assessment, audit, content, harms, intake, triage
from .auth import Principal, current_principal
from .authz import decide
from .config import settings
from .db import global_tx, tenant_tx

NOTICE = ("OpenDPO is a proof of concept. It provides no legal advice and is not a "
          "substitute for review by qualified privacy, legal and compliance professionals.")

log = logging.getLogger("opendpo")
_library: content.Library | None = None


def library() -> content.Library:
    global _library
    if _library is None:
        _library = content.load()
    return _library


def publish_content_to_policy_engine(retries: int = 30) -> None:
    """Load only usable (verified) rules into OPA. Unverified rules never reach it (CNT-01)."""
    data = library().opa_data()
    for _ in range(retries):
        try:
            httpx.put(f"{settings.opa_url}/v1/data/opendpo/content", json=data, timeout=3).raise_for_status()
            log.warning("published %d verified rules to the policy engine", len(data["rules"]))
            return
        except httpx.HTTPError:
            time.sleep(2)
    log.error("could not publish content to the policy engine")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    unplaced = intake.unplaced(library(), form())   # form() raises if the layout is inconsistent
    if unplaced:
        raise RuntimeError(f"intake.yaml places no question for {unplaced}; rules testing them could never fire")
    assessment.load_template(library())      # raise if the template or method is inconsistent
    assessment.load_methodology(library())
    harms.load(library(), {t.id for t in assessment.load_template(library()).framework_tags})
    threading.Thread(target=publish_content_to_policy_engine, daemon=True).start()
    yield


app = FastAPI(title="OpenDPO API", version="0.1.0", description=NOTICE, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                   allow_methods=["GET", "POST", "PUT"], allow_headers=["Authorization", "Content-Type"])

# Actions the web app asks about to decide what to show a user.
UI_ACTIONS = ["intake.submit", "intake.read", "intake.clarify", "triage.confirm", "draft.edit", "assessment.read",
              "assessment.approve", "assessment.submit", "assessment.accept_risk", "inventory.read", "policy.read",
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


@app.get("/api/content")
def content_status(p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """Every pack and rule, with whether the rule may be used and why not (USE-05, CNT-04)."""
    lib = library()
    packs = []
    for pack in lib.packs:
        records = lib.verifications[pack.id]
        sources = {s.id: s for s in pack.sources}
        packs.append({
            "id": pack.id, "title": pack.title, "version": pack.version, "as_of": pack.as_of,
            "lifecycle": pack.lifecycle, "jurisdiction": pack.jurisdiction,
            "sources": [s.model_dump() for s in pack.sources],
            "provisions": [{
                "id": pr.id, "citation": pr.citation, "summary": pr.summary, "text": pr.text,
                "source_url": sources[pr.source].url, "location": pr.location,
                "verified": content.provision_status(pr, records.get(pr.id)) is None,
                "verification": records[pr.id].model_dump() if pr.id in records else None,
            } for pr in pack.provisions],
            "rules": [{
                "id": st.rule.id, "title": st.rule.title, "kind": st.rule.kind,
                "provisions": st.rule.provisions, "explanation": st.rule.explanation,
                "usable": st.usable, "problems": st.problems,
            } for st in lib.statuses if st.pack.id == pack.id],
        })
    return {"notice": "Rules change. Regulatory content shows its as-of date and source and must be "
                      "verified before relying on it.",
            "usable_rules": len(lib.usable_rules), "total_rules": len(lib.statuses), "packs": packs}


# ---------------------------------------------------------------------------
# Intake and triage (WF-01 to WF-08)
# ---------------------------------------------------------------------------

_form: intake.Form | None = None
RULES_ENGINE = "rules-engine"


def form() -> intake.Form:
    global _form
    if _form is None:
        _form = intake.build(library())
    return _form


class AnswersIn(BaseModel):
    answers: dict[str, Any] = {}


class ClarificationIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class ChangeIn(BaseModel):
    action: Literal["add", "remove"]
    rule: str | None = None       # remove: the rule whose result the analyst sets aside
    item: str | None = None       # add: what the analyst adds, in words
    reason: str = Field(min_length=3, max_length=2000)


class DecisionIn(BaseModel):
    decision: Literal["confirm", "change"]
    changes: list[ChangeIn] = []
    note: str | None = Field(None, max_length=4000)


def scoping_answers(conn, tenant_id: UUID) -> dict[str, Any]:
    row = conn.execute("SELECT answers FROM tenant_scoping WHERE tenant_id = %s", (tenant_id,)).fetchone()
    scoping_ids = {f.id for p in library().packs for f in p.facts if f.asked_in == "scoping"}
    return {k: v for k, v in (row["answers"] if row else {}).items() if k in scoping_ids}


def known_answers(answers: dict[str, Any]) -> dict[str, Any]:
    ids = form().by_id()
    return {k: v for k, v in answers.items() if k in ids}


def load_project(conn, project_id: UUID) -> dict:
    row = conn.execute("SELECT * FROM project WHERE id = %s", (project_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return row


def answers_digest(answers: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(answers, sort_keys=True).encode("utf-8")).hexdigest()


@app.get("/api/tenants/{tenant_id}/intake/form")
def intake_form(tenant_id: UUID, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """The intake form as JSON Schema, each pack question with the definitions behind it."""
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "intake.read")
    with tenant_tx(tenant_id) as conn:
        scoping = scoping_answers(conn, tenant_id)
    return {"schema": form().json_schema(), "scoping": scoping, "ai_question": intake.AI_QUESTION,
            "content_versions": library().versions(), "notice": NOTICE}


@app.get("/api/tenants/{tenant_id}/projects")
def list_projects(tenant_id: UUID, p: Principal = Depends(current_principal)) -> list[dict[str, Any]]:
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "intake.read")
    with tenant_tx(tenant_id) as conn:
        return conn.execute(
            """SELECT pr.id, pr.name, pr.status, pr.updated_at, u.display_name AS created_by_name,
                      (SELECT max(version) FROM intake_submission s WHERE s.project_id = pr.id) AS version
               FROM project pr JOIN app_user u ON u.id = pr.created_by
               ORDER BY pr.updated_at DESC""").fetchall()


@app.post("/api/tenants/{tenant_id}/projects", status_code=status.HTTP_201_CREATED)
def create_project(tenant_id: UUID, body: AnswersIn, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "intake.submit", log_denial=True)
    answers = known_answers(body.answers)
    name = str(answers.get("project.name") or "Untitled project")[:200]
    project_id = uuid4()
    with tenant_tx(tenant_id) as conn:
        conn.execute("""INSERT INTO project (id, tenant_id, name, answers, created_by)
                        VALUES (%s, %s, %s, %s, %s)""", (project_id, tenant_id, name, Jsonb(answers), p.user_id))
        audit.append(conn, tenant_id, audit_actor(actor), "project.created", object_type="project",
                     object_id=str(project_id), payload={"name": name})
    return {"id": project_id, "name": name, "status": "draft"}


@app.get("/api/tenants/{tenant_id}/projects/{project_id}")
def project_detail(tenant_id: UUID, project_id: UUID, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "intake.read")
    with tenant_tx(tenant_id) as conn:
        pr = load_project(conn, project_id)
        subs = conn.execute(
            """SELECT s.version, s.submitted_at, u.display_name AS submitted_by_name
               FROM intake_submission s JOIN app_user u ON u.id = s.submitted_by
               WHERE s.project_id = %s ORDER BY s.version DESC""", (project_id,)).fetchall()
        run = conn.execute(
            """SELECT r.id, r.status, r.result, r.content_versions, r.created_at, r.decision, r.decided_at,
                      s.version AS submission_version, u.display_name AS decided_by_name
               FROM triage_run r JOIN intake_submission s ON s.id = r.submission_id
               LEFT JOIN app_user u ON u.id = r.decided_by
               WHERE r.project_id = %s ORDER BY r.created_at DESC LIMIT 1""", (project_id,)).fetchone()
        creator = conn.execute("SELECT display_name FROM app_user WHERE id = %s", (pr["created_by"],)).fetchone()
    return {**pr, "created_by_name": creator["display_name"] if creator else None,
            "submissions": subs, "triage": run}


@app.put("/api/tenants/{tenant_id}/projects/{project_id}/answers")
def save_answers(tenant_id: UUID, project_id: UUID, body: AnswersIn,
                 p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """Save the working copy. Saving is not submitting; nothing is triaged."""
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "intake.submit", log_denial=True)
    answers = known_answers(body.answers)
    with tenant_tx(tenant_id) as conn:
        pr = load_project(conn, project_id)
        if pr["status"] == "confirmed":
            raise HTTPException(status.HTTP_409_CONFLICT, "triage is confirmed; this intake can no longer change")
        name = str(answers.get("project.name") or pr["name"])[:200]
        conn.execute("UPDATE project SET answers = %s, name = %s, updated_at = now() WHERE id = %s",
                     (Jsonb(answers), name, project_id))
    return {"saved": True, "problems": form().validate(answers)}


@app.post("/api/tenants/{tenant_id}/projects/{project_id}/submit")
def submit_intake(tenant_id: UUID, project_id: UUID, p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """WF-04, WF-05, WF-08: record the answers as a new version, then run triage unless
    the AI question is "not sure", which waits for an analyst."""
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "intake.submit", log_denial=True)
    with tenant_tx(tenant_id) as conn:
        pr = load_project(conn, project_id)
        if pr["status"] == "confirmed":
            raise HTTPException(status.HTTP_409_CONFLICT, "triage is already confirmed for this project")
        problems = form().validate(pr["answers"])
        if problems:
            raise HTTPException(422, {"problems": problems})
        answers = form().prune(pr["answers"])
        scoping = scoping_answers(conn, tenant_id)
        version = conn.execute("SELECT coalesce(max(version), 0) + 1 AS v FROM intake_submission "
                               "WHERE project_id = %s", (project_id,)).fetchone()["v"]
        sub = conn.execute(
            """INSERT INTO intake_submission (tenant_id, project_id, version, answers, scoping, form_version, submitted_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (tenant_id, project_id, version, Jsonb(answers), Jsonb(scoping), form().layout.version, p.user_id)
        ).fetchone()
        audit.append(conn, tenant_id, audit_actor(actor), "intake.submitted", object_type="project",
                     object_id=str(project_id),
                     payload={"version": version, "answers_sha256": answers_digest(answers)})
        conn.execute("UPDATE triage_run SET status = 'superseded' WHERE project_id = %s AND status = 'proposed'",
                     (project_id,))
        if answers.get(intake.AI_QUESTION) == intake.NOT_SURE:
            conn.execute("""UPDATE project SET status = 'awaiting_clarification', updated_at = now()
                            WHERE id = %s""", (project_id,))
            audit.append(conn, tenant_id, audit_actor(actor), "triage.waiting", object_type="project",
                         object_id=str(project_id),
                         payload={"reason": "AI use is not sure; an analyst follows up before triage (WF-08)"})
            return {"status": "awaiting_clarification", "version": version}
        facts = {**scoping, **answers}
        try:
            result = triage.run(library(), facts)
        except triage.PolicyEngineUnavailable as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
        run_id = uuid4()
        conn.execute(
            """INSERT INTO triage_run (id, tenant_id, project_id, submission_id, facts, result, content_versions)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (run_id, tenant_id, project_id, sub["id"], Jsonb(facts), Jsonb(result), Jsonb(result["content_versions"])))
        conn.execute("""UPDATE project SET status = 'triaged', clarification = NULL, updated_at = now()
                        WHERE id = %s""", (project_id,))
        audit.append(conn, tenant_id, audit.Actor("system", RULES_ENGINE, (), on_behalf_of=actor["id"]),
                     "triage.ran", object_type="triage_run", object_id=str(run_id),
                     payload={"project": str(project_id), "version": version, **triage.summary(result)},
                     content_versions=result["content_versions"])
    return {"status": "triaged", "version": version, "triage_run": run_id, "result": result}


@app.post("/api/tenants/{tenant_id}/projects/{project_id}/clarification")
def ask_clarification(tenant_id: UUID, project_id: UUID, body: ClarificationIn,
                      p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """WF-08: an analyst asks the submitter to settle a "not sure" answer."""
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "intake.clarify", log_denial=True)
    with tenant_tx(tenant_id) as conn:
        pr = load_project(conn, project_id)
        if pr["status"] != "awaiting_clarification":
            raise HTTPException(status.HTTP_409_CONFLICT, "this project is not waiting for a clarification")
        conn.execute("UPDATE project SET clarification = %s, updated_at = now() WHERE id = %s",
                     (body.question, project_id))
        audit.append(conn, tenant_id, audit_actor(actor), "intake.clarification_requested", object_type="project",
                     object_id=str(project_id), payload={"question": body.question})
    return {"status": "awaiting_clarification", "clarification": body.question}


@app.post("/api/tenants/{tenant_id}/projects/{project_id}/triage/{run_id}/decision")
def decide_triage(tenant_id: UUID, project_id: UUID, run_id: UUID, body: DecisionIn,
                  p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """WF-06: an analyst confirms the rules' result or changes it. A change never edits
    the rules' result; it is recorded beside it, with a reason for each item."""
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "triage.confirm", log_denial=True)
    if body.decision == "change" and not body.changes:
        raise HTTPException(422, "a change needs at least one item")
    if body.decision == "confirm" and body.changes:
        raise HTTPException(422, "confirming as is takes no changes")
    with tenant_tx(tenant_id) as conn:
        run = conn.execute("SELECT * FROM triage_run WHERE id = %s AND project_id = %s",
                           (run_id, project_id)).fetchone()
        if run is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "triage run not found")
        if run["status"] != "proposed":
            raise HTTPException(status.HTTP_409_CONFLICT, f"this triage run is {run['status']}, not awaiting a decision")
        matched = {e["rule"] for k in ("classifications", "obligations") for e in run["result"][k]}
        matched |= {t["rule"] for a in run["result"]["assessments"] for t in a["triggered_by"]}
        for c in body.changes:
            if c.action == "remove" and c.rule not in matched:
                raise HTTPException(422, f"{c.rule} is not in this triage result")
            if c.action == "add" and not (c.item and c.item.strip()):
                raise HTTPException(422, "an added item needs a description")
        decision = body.model_dump()
        conn.execute("""UPDATE triage_run SET status = 'confirmed', decision = %s, decided_by = %s, decided_at = now()
                        WHERE id = %s""", (Jsonb(decision), p.user_id, run_id))
        conn.execute("UPDATE project SET status = 'confirmed', updated_at = now() WHERE id = %s", (project_id,))
        audit.append(conn, tenant_id, audit_actor(actor), "triage.confirmed" if body.decision == "confirm"
                     else "triage.changed", object_type="triage_run", object_id=str(run_id),
                     payload={"project": str(project_id), **decision},
                     content_versions=run["content_versions"])
    return {"status": "confirmed", "decision": decision}


# Assessments (WF-11 onward) live in their own module; it uses the helpers above.
from .assessments_api import router as assessments_router  # noqa: E402

from .inventory_api import router as inventory_router  # noqa: E402

from .review_api import router as review_router  # noqa: E402

app.include_router(assessments_router)
app.include_router(inventory_router)
app.include_router(review_router)
