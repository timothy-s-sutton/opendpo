"""Assessment endpoints (WF-11, WF-15, WF-19, WF-20).

An analyst opens an assessment from a confirmed triage run. People edit one section at a
time; each save is a new revision checked against the rest of the assessment, and the
ratings, routing level and blockers are always computed, never typed in. The agent will
write its draft through the same path, as revision 1 of each section.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from . import assessment as engine
from . import audit, harms
from .auth import Principal, current_principal
from .db import tenant_tx
from .inventory_api import current_policies
from .main import NOTICE, audit_actor, library, load_project, load_tenant, require

router = APIRouter()
EDITABLE_STATUSES = ("draft", "returned")


def template() -> engine.Template:
    return engine.load_template(library())


def methodology() -> engine.Methodology:
    return engine.load_methodology(library())


def harm_list() -> harms.Harms:
    return harms.load(library(), {t.id for t in template().framework_tags})


class CreateIn(BaseModel):
    assessment: str | None = None     # which triggered assessment, when triage found more than one
    processing_activity: UUID | None = None   # the inventory record this assessment covers


class SectionIn(BaseModel):
    body: dict[str, Any]
    base_revision: int = Field(ge=0)  # the revision the editor started from; 0 for a new section
    note: str | None = Field(None, max_length=2000)


def current_state(conn, assessment_id: UUID) -> dict[str, dict[str, Any]]:
    """Latest revision of each section that has one."""
    rows = conn.execute(
        """SELECT DISTINCT ON (section) section, revision, body, author_type, author_id, created_at
           FROM assessment_revision WHERE assessment_id = %s
           ORDER BY section, revision DESC""", (assessment_id,)).fetchall()
    return {r["section"]: r for r in rows}


def load_assessment(conn, assessment_id: UUID) -> dict:
    row = conn.execute("SELECT * FROM assessment WHERE id = %s", (assessment_id,)).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "assessment not found")
    return row


def method_of(a: dict) -> engine.Methodology:
    """The method as it was when the assessment was opened (PLT-13)."""
    return engine.Methodology.model_validate(a["methodology"])


def triggered(run: dict) -> list[str]:
    """Assessments the confirmed triage result calls for, less any the analyst set aside."""
    removed = {c["rule"] for c in (run["decision"] or {}).get("changes", []) if c.get("action") == "remove"}
    return [a["assessment"] for a in run["result"]["assessments"]
            if any(t["rule"] not in removed for t in a["triggered_by"])]


@router.post("/api/tenants/{tenant_id}/projects/{project_id}/assessments", status_code=status.HTTP_201_CREATED)
def create_assessment(tenant_id: UUID, project_id: UUID, body: CreateIn,
                      p: Principal = Depends(current_principal)) -> dict[str, Any]:
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "draft.edit", log_denial=True)
    tpl, method = template(), methodology()
    with tenant_tx(tenant_id) as conn:
        load_project(conn, project_id)
        run = conn.execute("""SELECT * FROM triage_run WHERE project_id = %s AND status = 'confirmed'
                              ORDER BY decided_at DESC LIMIT 1""", (project_id,)).fetchone()
        if run is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "an analyst must confirm triage before an assessment starts")
        kinds = triggered(run)
        if not kinds:
            raise HTTPException(status.HTTP_409_CONFLICT, "the confirmed triage result calls for no assessment")
        kind = body.assessment or (kinds[0] if len(kinds) == 1 else None)
        if kind not in kinds:
            raise HTTPException(422, {"choose_one_of": kinds})
        existing = conn.execute("SELECT id FROM assessment WHERE triage_run_id = %s AND assessment_type = %s",
                                (run["id"], kind)).fetchone()
        if existing:
            raise HTTPException(status.HTTP_409_CONFLICT, {"assessment": str(existing["id"]),
                                                            "message": "this assessment is already open"})
        if body.processing_activity is not None and conn.execute(
                "SELECT 1 FROM processing_activity WHERE id = %s", (body.processing_activity,)).fetchone() is None:
            raise HTTPException(422, "no such processing activity in this tenant")
        floor, floor_rules = engine.floor_from_triage(run["result"], run["decision"], method)
        used = [{"policy": v["template_id"] or str(v["policy_id"]), "title": v["title"], "version": v["version"],
                 "version_id": str(v["version_id"])} for v in current_policies(conn)]
        aid = uuid4()
        conn.execute(
            """INSERT INTO assessment (id, tenant_id, project_id, triage_run_id, assessment_type, template_id,
                                       template_version, methodology, content_versions, routing_floor,
                                       floor_rules, created_by, processing_activity_id, policy_versions)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (aid, tenant_id, project_id, run["id"], kind, tpl.id, tpl.version, Jsonb(method.model_dump(mode="json")),
             Jsonb(library().versions()), floor, Jsonb(floor_rules), p.user_id, body.processing_activity,
             Jsonb(used)))
        audit.append(conn, tenant_id, audit_actor(actor), "assessment.created", object_type="assessment",
                     object_id=str(aid),
                     payload={"project": str(project_id), "triage_run": str(run["id"]), "type": kind,
                              "template": f"{tpl.id}@{tpl.version}", "methodology": f"{method.id}@{method.version}",
                              "routing_floor": floor, "floor_rules": floor_rules,
                              "processing_activity": str(body.processing_activity) if body.processing_activity else None,
                              "policy_versions": used},
                     content_versions=library().versions())
    return {"id": aid, "type": kind, "routing_floor": floor, "floor_rules": floor_rules}


@router.get("/api/tenants/{tenant_id}/assessments")
def list_assessments(tenant_id: UUID, project: UUID | None = None,
                     p: Principal = Depends(current_principal)) -> list[dict[str, Any]]:
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "assessment.read")
    with tenant_tx(tenant_id) as conn:
        return conn.execute(
            """SELECT a.id, a.project_id, pr.name AS project_name, a.assessment_type, a.status, a.routing_floor,
                      a.created_at, a.updated_at
               FROM assessment a JOIN project pr ON pr.id = a.project_id
               WHERE %s::uuid IS NULL OR a.project_id = %s
               ORDER BY a.updated_at DESC""", (project, project)).fetchall()


@router.get("/api/tenants/{tenant_id}/assessments/{assessment_id}")
def assessment_detail(tenant_id: UUID, assessment_id: UUID,
                      p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """The whole assessment: each section with its law and current content, plus everything
    computed from it."""
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "assessment.read")
    tpl, lib = template(), library()
    with tenant_tx(tenant_id) as conn:
        a = load_assessment(conn, assessment_id)
        state = current_state(conn, assessment_id)
        names = {r["id"]: r["display_name"] for r in conn.execute("SELECT id::text, display_name FROM app_user")}
    method = method_of(a)
    bodies = {sid: r["body"] for sid, r in state.items()}
    sections = []
    for s in tpl.sections:
        cur = state.get(s.id)
        sections.append({
            "id": s.id, "number": s.number, "title": s.title, "kind": s.kind, "help": s.help,
            "editable": s.editable, "in_regulator_report": s.in_regulator_report,
            "what_the_law_says": engine.citations(lib, s.provisions),
            "revision": cur["revision"] if cur else 0,
            "body": cur["body"] if cur else None,
            "last_edited_by": (names.get(cur["author_id"], cur["author_id"]) if cur else None),
            "last_edited_by_type": cur["author_type"] if cur else None,
            "last_edited_at": cur["created_at"] if cur else None,
        })
    return {
        "id": a["id"], "project_id": a["project_id"], "type": a["assessment_type"], "status": a["status"],
        "title": tpl.title, "template": {"id": a["template_id"], "version": a["template_version"]},
        "basis": engine.citations(lib, tpl.basis),
        "methodology": a["methodology"], "content_versions": a["content_versions"],
        "framework": tpl.framework, "framework_tags": [t.model_dump() for t in tpl.framework_tags],
        "risk_acceptances": a["risk_acceptances"], "sections": sections,
        "harms": harm_view(lib),
        "computed": engine.derive(bodies, tpl, method, a["routing_floor"], a["risk_acceptances"]),
        "floor_rules": a["floor_rules"], "editable": a["status"] in EDITABLE_STATUSES, "notice": NOTICE,
        "processing_activity_id": a["processing_activity_id"], "policy_versions": a["policy_versions"],
    }


def harm_view(lib) -> dict[str, Any]:
    """The harm list with each entry's sign-off status and the law behind it (WF-25)."""
    hs = harm_list()
    index = lib.provision_index()
    return {"id": hs.id, "version": hs.version, "entries": [{
        "id": s.harm.id, "name": s.harm.name, "description": " ".join(s.harm.description.split()),
        "citation": index[s.harm.named_by][1].citation + s.harm.clause, "quote": " ".join(s.harm.quote.split()),
        "related": [{"provision": link.provision, "citation": index[link.provision][1].citation, "why": link.why}
                    for link in s.harm.related],
        "framework_tags": s.harm.framework_tags, "usable": s.usable, "problems": s.problems,
    } for s in hs.statuses]}


@router.put("/api/tenants/{tenant_id}/assessments/{assessment_id}/sections/{section_id}")
def save_section(tenant_id: UUID, assessment_id: UUID, section_id: str, body: SectionIn,
                 p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """WF-15: save a section as a new revision. The save is refused if someone else saved
    the section since the editor loaded it, or if it would leave the assessment inconsistent."""
    tenant = load_tenant(p, tenant_id)
    actor = require(p, tenant, "draft.edit", log_denial=True)
    tpl = template()
    section = tpl.section(section_id)
    if section is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such section")
    tags = {t.id for t in tpl.framework_tags}
    try:
        parsed = engine.parse(section, body.body, tags, set(harm_list().usable()))
    except engine.Rejected as exc:
        raise HTTPException(422, {"problems": exc.problems}) from exc
    with tenant_tx(tenant_id) as conn:
        a = conn.execute("SELECT * FROM assessment WHERE id = %s FOR UPDATE", (assessment_id,)).fetchone()
        if a is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "assessment not found")
        if a["status"] not in EDITABLE_STATUSES:
            raise HTTPException(status.HTTP_409_CONFLICT, f"this assessment is {a['status']}; it cannot be edited")
        state = current_state(conn, assessment_id)
        latest = state[section_id]["revision"] if section_id in state else 0
        if body.base_revision != latest:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                {"message": "this section changed since you opened it; reload to see the latest",
                                 "latest_revision": latest})
        if section_id in state and state[section_id]["body"] == parsed:
            return {"saved": False, "revision": latest, "message": "nothing changed"}
        proposed = {sid: r["body"] for sid, r in state.items()} | {section_id: parsed}
        problems = engine.check(proposed, tpl, method_of(a), a["risk_acceptances"])
        if problems:
            raise HTTPException(422, {"problems": problems})
        revision = latest + 1
        conn.execute(
            """INSERT INTO assessment_revision (tenant_id, assessment_id, section, revision, body,
                                                author_type, author_id, note)
               VALUES (%s, %s, %s, %s, %s, 'user', %s, %s)""",
            (tenant_id, assessment_id, section_id, revision, Jsonb(parsed), str(p.user_id), body.note))
        conn.execute("UPDATE assessment SET updated_at = now() WHERE id = %s", (assessment_id,))
        audit.append(conn, tenant_id, audit_actor(actor), "assessment.section_revised", object_type="assessment",
                     object_id=str(assessment_id),
                     payload={"section": section_id, "revision": revision, "sha256": engine.digest(parsed),
                              "note": body.note})
    return {"saved": True, "revision": revision}


@router.get("/api/tenants/{tenant_id}/assessments/{assessment_id}/sections/{section_id}/revisions")
def section_history(tenant_id: UUID, assessment_id: UUID, section_id: str,
                    p: Principal = Depends(current_principal)) -> dict[str, Any]:
    """WF-15: every revision of a section, what each one changed, and how the current
    version differs from the first draft."""
    tenant = load_tenant(p, tenant_id)
    require(p, tenant, "assessment.read")
    section = template().section(section_id)
    if section is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such section")
    with tenant_tx(tenant_id) as conn:
        load_assessment(conn, assessment_id)
        rows = conn.execute(
            """SELECT r.revision, r.body, r.author_type, r.author_id, r.on_behalf_of, r.note, r.created_at,
                      coalesce(u.display_name, r.author_id) AS author_name
               FROM assessment_revision r LEFT JOIN app_user u ON u.id::text = r.author_id
               WHERE r.assessment_id = %s AND r.section = %s ORDER BY r.revision""",
            (assessment_id, section_id)).fetchall()
    history, prev = [], None
    for r in rows:
        history.append({**r, "changes": engine.diff(section.kind, prev, r["body"])})
        prev = r["body"]
    since_first = engine.diff(section.kind, rows[0]["body"], rows[-1]["body"]) if len(rows) > 1 else None
    return {"section": section_id, "revisions": history,
            "first_author_type": rows[0]["author_type"] if rows else None, "since_first": since_first}
