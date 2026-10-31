"""Two outputs from one assessment (WF-16, WF-21, USE-03).

- Internal assessment: every section, the risk register with ratings, the appendices (the
  obligations checklist and the policy check), risk acceptances, and what the assessment was
  made with: content packs, policies, method, template, triage result and edit history.
- Regulator-ready report: only the sections the template marks for it. It leaves out the
  benefits and the risk register, lists safeguards without the risks they map to, and does not
  name legal counsel who gave legal advice (§ 7152(a)(8)-(9)). Until § 7157 is in a verified
  pack, the report says its contents follow OpenDPO's requirements and still need checking.

Both carry the intended-use notice and the named reviewers and approvers (USE-03). Rendering is
plain, self-contained HTML that prints cleanly to PDF from a browser.
"""
from __future__ import annotations

from html import escape
from typing import Any, Literal

Kind = Literal["internal", "regulator"]
LEVEL = {"very_low": "Very low", "low": "Low", "moderate": "Moderate", "high": "High", "very_high": "Very high"}
STATUS = {"met": "Met", "not_met": "Not met", "not_yet_due": "Not yet due", "not_applicable": "Does not apply",
          "unknown": "Unknown"}
REGULATOR_PENDING = ("The contents of this report follow OpenDPO's requirements (WF-21). They have not yet "
                     "been checked against the submission rules in the CCPA Regulations, § 7157.")


def build(detail: dict[str, Any], kind: Kind, history: list[dict[str, Any]], triage: dict[str, Any],
          tenant_name: str, project_name: str) -> dict[str, Any]:
    """The report as data: what the HTML and JSON both render."""
    secs = {s["id"]: s for s in detail["sections"]}
    approved = detail["status"] == "approved"
    keep = [s for s in detail["sections"] if s["body"] is not None or s["kind"] == "approval"]
    if kind == "regulator":
        keep = [s for s in keep if s["in_regulator_report"] and not s.get("appendix")]
    ratings = {r["risk"]: r for r in detail["computed"]["ratings"]}
    out_sections = []
    for s in keep:
        body = s["body"]
        if s["kind"] == "safeguards" and kind == "regulator" and body:
            body = {"safeguards": [{k: v for k, v in g.items() if k not in ("addresses", "policy_refs")}
                                   for g in body["safeguards"]]}
        if s["kind"] == "approval" and body and kind == "regulator":
            counsel = [r for r in body["reviewers"] if r["legal_counsel"]]
            body = {**body, "reviewers": [r for r in body["reviewers"] if not r["legal_counsel"]],
                    "counsel_omitted": bool(counsel)}
        if s["kind"] == "risk_register" and body:
            body = {"risks": [{**r, "inherent": ratings[r["id"]]["inherent"], "residual": ratings[r["id"]]["residual"]}
                              for r in body["risks"]]}
        out_sections.append({"id": s["id"], "number": s["number"], "title": s["title"], "kind": s["kind"],
                             "appendix": s.get("appendix", False), "body": body,
                             "law": [c["citation"] for c in s["what_the_law_says"]]})
    report = {
        "kind": kind,
        "title": ("Risk assessment report" if kind == "regulator" else "Internal risk assessment") + f": {project_name}",
        "organization": tenant_name, "status": detail["status"], "approved": approved,
        "approved_on": secs["approval"]["body"]["approved_on"] if secs["approval"]["body"] else None,
        "notice": detail["notice"], "ai_draft_label": detail.get("ai_draft_label"),
        "sections": out_sections,
        "risk_acceptances": detail["risk_acceptances"] if kind == "internal" else [],
        "pending_verification": REGULATOR_PENDING if kind == "regulator" else None,
    }
    if kind == "internal":
        report["made_with"] = {
            "content_versions": detail["content_versions"], "policy_versions": detail["policy_versions"],
            "methodology": f"{detail['methodology']['id']} {detail['methodology']['version']}",
            "template": f"{detail['template']['id']} version {detail['template']['version']}",
            "routing": detail["computed"]["routing"], "overall_inherent": detail["computed"]["overall_inherent"],
            "overall_residual": detail["computed"]["overall_residual"],
            "next_review_due": detail["review"]["next_review_due"],
        }
        report["triage"] = [{"rule": e["rule"], "title": e["title"],
                             "citations": [c["citation"] for c in e.get("citations", [])]}
                            for k in ("classifications", "obligations") for e in triage.get(k, [])]
        report["history"] = history
        report["decisions"] = detail["review"]["decisions"]
    return report


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

CSS = """
body{font-family:Georgia,'Times New Roman',serif;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#1b1b1b;
line-height:1.55;background:#fff}
h1{font-size:1.6rem;margin:0 0 .3rem}h2{font-size:1.2rem;margin:2rem 0 .5rem;border-bottom:1px solid #ccc;
padding-bottom:.2rem}h3{font-size:1rem;margin:1.2rem 0 .3rem}
.meta{color:#555;font-size:.9rem}.law{color:#666;font-size:.8rem;margin:.2rem 0 .6rem}
.banner{border:1px solid #b88a2a;background:#fbf4e4;padding:.6rem .8rem;margin:1rem 0;font-size:.9rem}
.notice{border-top:1px solid #ccc;margin-top:2.5rem;padding-top:.8rem;color:#555;font-size:.85rem}
table{border-collapse:collapse;width:100%;font-size:.88rem;margin:.5rem 0}
th,td{border:1px solid #ccc;padding:.35rem .5rem;text-align:left;vertical-align:top}th{background:#f3f3f3}
.pre{white-space:pre-wrap}
@media print{.banner{break-inside:avoid}h2{break-after:avoid}}
"""


def _p(text: str | None) -> str:
    """Paragraphs separated by blank lines; runs of lines starting with "- " become a list."""
    out = []
    for block in (text or "").strip().split("\n\n"):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        if lines and all(ln.lstrip().startswith("- ") for ln in lines):
            out.append(_list([ln.lstrip()[2:] for ln in lines]))
        elif lines and lines[0].endswith(":") and all(ln.lstrip().startswith("- ") for ln in lines[1:]) and lines[1:]:
            out.append(f"<p>{escape(lines[0])}</p>" + _list([ln.lstrip()[2:] for ln in lines[1:]]))
        elif lines:
            out.append(f"<p>{'<br>'.join(escape(ln) for ln in lines)}</p>")
    return "\n".join(out)


def _list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>" if items else ""


def _section(s: dict[str, Any], kind: Kind) -> str:
    b = s["body"] or {}
    out = [f"<h2>{escape(s['number'])}. {escape(s['title'])}</h2>"]
    if s["law"]:
        out.append(f'<div class="law">{escape("; ".join(s["law"]))}</div>')
    k = s["kind"]
    if k == "text":
        out.append(_p(b.get("text")))
    elif k == "risk_register":
        out.append("<table><tr><th>Risk</th><th>Source and cause</th><th>Before safeguards</th>"
                   "<th>After safeguards</th><th>Cites</th></tr>")
        for r in b.get("risks", []):
            cites = ", ".join(([r["harm"]] if r.get("harm") else []) + r.get("citations", []) + r.get("policy_refs", []))
            out.append(f"<tr><td>{escape(r['id'])}. {escape(r['title'])}</td><td>{escape(r['source_and_cause'])}</td>"
                       f"<td>{LEVEL[r['inherent']]}</td><td>{LEVEL.get(r.get('residual') or '', 'Not rated')}</td>"
                       f"<td>{escape(cites)}</td></tr>")
        out.append("</table>")
    elif k == "safeguards":
        out.append("<table><tr><th>Safeguard</th><th>Status</th><th>Owner</th>"
                   + ("<th>Addresses</th>" if kind == "internal" else "") + "</tr>")
        for g in b.get("safeguards", []):
            out.append(f"<tr><td><strong>{escape(g['title'])}</strong><br>{escape(g.get('description') or '')}</td>"
                       f"<td>{'In place' if g['status'] == 'in_place' else 'Planned'}</td>"
                       f"<td>{escape(g.get('owner') or '')}</td>"
                       + (f"<td>{escape(', '.join(g.get('addresses', [])))}</td>" if kind == "internal" else "")
                       + "</tr>")
        out.append("</table>")
    elif k == "decision":
        verdict = {"yes": "Yes, the business will go ahead with the processing.",
                   "no": "No, the business will not go ahead with the processing.",
                   "undecided": "Not yet decided."}[b.get("initiate", "undecided")]
        out.append(f"<p><strong>{verdict}</strong></p>")
        if kind == "internal":
            out.append(_p(b.get("rationale")))
    elif k == "people":
        out.append(_list([f"{x['name']}, {x['position']}" + (f": {x['provided']}" if x.get("provided") else "")
                          for x in b.get("people", [])]))
    elif k == "approval":
        if not s["body"]:
            out.append("<p>Not yet approved.</p>")
        else:
            out.append(f"<p>Approved on {escape(b['approved_on'])}.</p>")
            def line(r: dict[str, Any]) -> str:
                what = "provisional approval" if r["step"] == "provisional" else "approval"
                authority = " · has authority to decide whether the processing goes ahead" \
                    if r["has_initiation_authority"] else ""
                return f"{r['name']}, {r['position']} ({what}, {r['date']}){authority}"
            out.append(_list([line(r) for r in b["reviewers"]]))
            if b.get("counsel_omitted"):
                out.append("<p class='meta'>Legal counsel who gave legal advice is not named, as § 7152(a)(9) allows.</p>")
    elif k == "checklist":
        out.append("<table><tr><th style='width:11rem'>Item</th><th style='width:6rem'>Status</th><th>Note</th></tr>")
        for i in b.get("items", []):
            out.append(f"<tr><td>{escape(i['ref'])}</td><td>{STATUS[i['status']]}</td><td>{escape(i['note'])}</td></tr>")
        out.append("</table>")
    return "\n".join(out)


def html(report: dict[str, Any]) -> str:
    kind = report["kind"]
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{escape(report['title'])}</title>"
             f"<meta name='viewport' content='width=device-width, initial-scale=1'><style>{CSS}</style></head><body>",
             f"<h1>{escape(report['title'])}</h1>",
             f"<div class='meta'>{escape(report['organization'])} · "
             + (f"Approved {escape(report['approved_on'])}" if report["approved"] else
                f"Status: {escape(report['status'].replace('_', ' '))}, not approved") + "</div>"]
    if not report["approved"]:
        parts.append("<div class='banner'><strong>Draft.</strong> This assessment has not been approved.</div>")
    if report.get("pending_verification"):
        parts.append(f"<div class='banner'>{escape(report['pending_verification'])}</div>")
    if kind == "internal" and report.get("ai_draft_label"):
        parts.append(f"<div class='banner'>{escape(report['ai_draft_label'])} The first version of each section "
                     "was drafted by OpenDPO's agent; the edit history below shows every change since.</div>")
    for s in report["sections"]:
        if s["appendix"] and not any(x["appendix"] for x in report["sections"][:report["sections"].index(s)]):
            parts.append("<h2 style='border:none;margin-top:3rem'>Appendices</h2>")
        parts.append(_section(s, kind))
    if kind == "internal":
        if report["risk_acceptances"]:
            parts.append("<h2>Risk acceptances</h2>")
            parts.append(_list([f"{a['risk']}. {a['risk_title']}: {LEVEL[a['residual']]} after safeguards, accepted by "
                                f"{a['by_name']} ({a.get('by_position') or 'position not recorded'}) on {a['at'][:10]}. "
                                f"Reason: {a['reason']} Review by {a['review_date']}." for a in report["risk_acceptances"]]))
        mw = report["made_with"]
        parts.append("<h2>What this assessment was made with</h2>")
        parts.append(_list(
            [f"Risk method: {mw['methodology']}; template: {mw['template']}",
             f"Highest risk before safeguards: {LEVEL.get(mw['overall_inherent'] or '', 'none')}; after: "
             f"{LEVEL.get(mw['overall_residual'] or '', 'none')}",
             f"Approval routing: {mw['routing']['level']} (triage floor {mw['routing']['floor']}, from the scores "
             f"{mw['routing']['from_score']})",
             f"Next scheduled review: {mw['next_review_due'] or 'set on approval'}"]
            + [f"Content pack {k} version {v}" for k, v in sorted(mw["content_versions"].items())]
            + [f"Policy: {p['title']}, version {p['version']}" for p in mw["policy_versions"]]))
        parts.append("<h3>Triage result</h3>")
        parts.append(_list([f"{t['rule']}: {t['title']} ({'; '.join(t['citations'])})" for t in report["triage"]]))
        parts.append("<h3>Review decisions</h3>")
        verb = {"approve": "approved", "return": "returned it", "reject": "rejected it"}
        parts.append(_list([f"Round {d['review_round']}: {d['name']} ({d['role'].replace('_', ' ')}) "
                            f"{verb[d['decision']]} on {str(d['decided_at'])[:10]}" + (f": {d['note']}" if d['note'] else "")
                            for d in report["decisions"]]) or "<p>None yet.</p>")
        parts.append("<h3>Edit history</h3>")
        drafts = [h for h in report["history"] if h["revision"] == 1 and h["author"].startswith("OpenDPO agent")]
        lines = []
        if drafts:
            how = (drafts[0].get("note") or "").split("Drafted by ")[-1].rstrip(".")
            lines.append(f"Revision 1 of {len(drafts)} sections: {drafts[0]['author']} on {str(drafts[0]['at'])[:10]}"
                         + (f" (drafted by {how})" if how else ""))
        lines += [f"{h['section'].replace('_', ' ')} revision {h['revision']}: {h['author']} on {str(h['at'])[:10]}"
                  + (f" ({h['note']})" if h.get("note") else "") for h in report["history"] if h not in drafts]
        parts.append(_list(lines))
    parts.append(f"<div class='notice'>{escape(report['notice'])}</div></body></html>")
    return "\n".join(parts)
