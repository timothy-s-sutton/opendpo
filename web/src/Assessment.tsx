import { useCallback, useEffect, useState } from "react";
import { api, openPage } from "./auth";
import {
  ASSESSMENT_STATUS, Assessment, AssessmentRow, CHECK_STATUS, CheckItem, LEVELS, LEVEL_LABELS, Level, LawCite, Person,
  ROUTING_LABELS, Revision, Reviewer, Risk, Safeguard, Section,
} from "./assessmentTypes";
import { ROLE_LABELS, Tenant } from "./types";

type Can = (a: string) => boolean;
const json = (body: unknown): RequestInit => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});
const roleList = (roles: string[], joiner = " and ") => roles.map((r) => ROLE_LABELS[r] ?? r).join(joiner);

// ---------------------------------------------------------------------------
// Starting an assessment from a confirmed project
// ---------------------------------------------------------------------------

export function AssessmentStart({ tenant, projectId, can, onOpen }: {
  tenant: Tenant; projectId: string; can: Can; onOpen: (id: string) => void;
}) {
  const [rows, setRows] = useState<AssessmentRow[] | null>(null);
  const [activities, setActivities] = useState<{ id: string; name: string }[]>([]);
  const [activity, setActivity] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<AssessmentRow[]>(`/api/tenants/${tenant.id}/assessments?project=${projectId}`).then(setRows)
      .catch((e: Error) => setErr(e.message));
    if (can("inventory.read")) {
      api<{ id: string; name: string }[]>(`/api/tenants/${tenant.id}/inventory/activities`).then((a) => {
        setActivities(a);
        if (a.length === 1) setActivity(a[0].id);
      }).catch(() => undefined);
    }
  }, [tenant.id, projectId, can]);

  const start = async () => {
    try {
      const r = await api<{ id: string }>(`/api/tenants/${tenant.id}/projects/${projectId}/assessments`,
        json({ processing_activity: activity || null }));
      onOpen(r.id);
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  if (!rows) return null;
  return (
    <div className="card">
      <h2>Risk assessment</h2>
      {rows.length > 0 ? (
        <ul className="plain">
          {rows.map((r) => (
            <li key={r.id}>
              <button className="link" onClick={() => onOpen(r.id)}>AI and automated decision risk assessment</button>{" "}
              <span className={`status a-${r.status}`}>{ASSESSMENT_STATUS[r.status]}</span>
            </li>
          ))}
        </ul>
      ) : can("draft.edit") ? (
        <>
          <p className="muted">Triage calls for a risk assessment. Link the inventory record it covers, so the draft
            can use what the inventory knows about the system, its data and who receives it.</p>
          <label className="q">Inventory record</label>
          <select value={activity} onChange={(e) => setActivity(e.target.value)}>
            <option value="">None</option>
            {activities.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <div className="actions"><button onClick={start}>Start the assessment</button></div>
        </>
      ) : <p className="muted">Waiting for a privacy analyst to start the assessment.</p>}
      {err && <p className="err">{err}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// The assessment
// ---------------------------------------------------------------------------

export function AssessmentView({ tenant, id, can, onBack }: { tenant: Tenant; id: string; can: Can; onBack: () => void }) {
  const [a, setA] = useState<Assessment | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const base = `/api/tenants/${tenant.id}/assessments/${id}`;
  const load = useCallback(() => {
    api<Assessment>(base).then(setA).catch((e: Error) => setErr(e.message));
  }, [base]);
  useEffect(load, [load]);

  const run = async (label: string, f: () => Promise<unknown>) => {
    setBusy(label);
    setErr(null);
    try {
      await f();
      load();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (!a) return err ? <p className="err">{err}</p> : <p className="loading">Loading…</p>;
  const empty = a.sections.every((s) => s.revision === 0);
  const ratings = Object.fromEntries(a.computed.ratings.map((r) => [r.risk, r]));
  const c = a.computed;

  return (
    <section>
      <button className="link" onClick={onBack}>← Back to the project</button>
      <h1>{a.title}</h1>
      <p className="muted">
        <span className={`status a-${a.status}`}>{ASSESSMENT_STATUS[a.status]}</span>{" "}
        <span className={`status risk-${c.routing.level}`}>{ROUTING_LABELS[c.routing.level]} risk</span>
        {a.review.next_review_due && <> · next review due {a.review.next_review_due}</>}
      </p>
      {a.ai_draft_label && <div className="card warn small-card">{a.ai_draft_label}</div>}

      <div className="actions wrap">
        {empty && can("draft.edit") && a.status === "draft" && (
          <button disabled={!!busy} onClick={() => run("draft", () => api(`${base}/draft`, json({})))}>
            {busy === "draft" ? "Drafting… this can take a minute" : "Draft with AI"}
          </button>
        )}
        {a.editable && !empty && can("assessment.submit") && (
          <button disabled={!!busy} onClick={() => run("submit", () => api(`${base}/submit`, json({})))}>
            Submit for review
          </button>
        )}
        {can("assessment.export") && (
          <>
            <button className="secondary" onClick={() => openPage(`${base}/export?kind=internal`).catch((e) => setErr(e.message))}>
              Internal assessment
            </button>
            {a.status === "approved" && (
              <button className="secondary"
                      onClick={() => openPage(`${base}/export?kind=regulator`).catch((e) => setErr(e.message))}>
                Regulator-ready report
              </button>
            )}
          </>
        )}
      </div>
      {err && <div className="card bad-soft"><p className="err">{err}</p></div>}

      <div className="grid2">
        <div className="card">
          <h2>Where it stands</h2>
          <dl className="facts">
            <dt>Highest risk before safeguards</dt><dd>{c.overall_inherent ? LEVEL_LABELS[c.overall_inherent] : "Not rated"}</dd>
            <dt>Highest risk after safeguards</dt><dd>{c.overall_residual ? LEVEL_LABELS[c.overall_residual] : "Not rated"}</dd>
            <dt>Approval routing</dt>
            <dd>{ROUTING_LABELS[c.routing.level]}{c.routing.floor === "high" && a.floor_rules.length > 0 &&
              <span className="muted small"> (high from triage: {a.floor_rules.join(", ")})</span>}</dd>
          </dl>
          {c.sections_not_started.length > 0 && (
            <p className="muted small">Not started: {c.sections_not_started.map((s) => a.sections.find((x) => x.id === s)?.title).join(", ")}</p>
          )}
          {[...c.consistency_problems, ...c.proceed_blockers.filter(() => sectionBody(a, "decision")?.initiate === "yes")]
            .map((p) => <p key={p} className="err small">{p}</p>)}
        </div>
        <div className="card">
          <h2>Risk map</h2>
          <RiskMap a={a} />
        </div>
      </div>

      <ReviewPanel a={a} tenant={tenant} can={can} run={run} busy={busy} />

      {a.sections.map((s) => (
        <SectionCard key={s.id} s={s} a={a} tenant={tenant} can={can} ratings={ratings} reload={load} base={base} />
      ))}
    </section>
  );
}

function sectionBody(a: Assessment, id: string) {
  return a.sections.find((s) => s.id === id)?.body;
}

// ---------------------------------------------------------------------------
// The 5-by-5 map: hollow chips before safeguards, solid chips after
// ---------------------------------------------------------------------------

function RiskMap({ a }: { a: Assessment }) {
  const risks: Risk[] = sectionBody(a, "risks")?.risks ?? [];
  const rows = [...LEVELS].reverse();
  const at = (lik: Level, sev: Level) => risks.flatMap((r) => [
    ...(r.likelihood === lik && r.severity === sev ? [{ id: r.id, after: false }] : []),
    ...(r.residual_likelihood === lik && r.residual_severity === sev ? [{ id: r.id, after: true }] : []),
  ]);
  if (risks.length === 0) return <p className="muted">No risks yet.</p>;
  return (
    <div>
      <div className="map">
        <div className="map-y">Likelihood</div>
        <div className="map-grid">
          {rows.map((lik) => (
            <div key={lik} className="map-row">
              <div className="map-label">{LEVEL_LABELS[lik]}</div>
              {LEVELS.map((sev, i) => {
                const level = a.methodology.matrix[lik][i];
                return (
                  <div key={sev} className={`map-cell lv-${level}`} title={`${LEVEL_LABELS[level]} risk`}>
                    {at(lik, sev).map((x) => <span key={x.id + x.after} className={`chip ${x.after ? "after" : "before"}`}>{x.id}</span>)}
                  </div>
                );
              })}
            </div>
          ))}
          <div className="map-row">
            <div className="map-label" />
            {LEVELS.map((sev) => <div key={sev} className="map-label col">{LEVEL_LABELS[sev]}</div>)}
          </div>
          <div className="map-x">Severity</div>
        </div>
      </div>
      <p className="muted small"><span className="chip before">r1</span> before safeguards ·{" "}
        <span className="chip after">r1</span> after safeguards</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Review and approval
// ---------------------------------------------------------------------------

function ReviewPanel({ a, tenant, can, run, busy }: {
  a: Assessment; tenant: Tenant; can: Can; run: (l: string, f: () => Promise<unknown>) => void; busy: string | null;
}) {
  const [note, setNote] = useState("");
  const [authority, setAuthority] = useState(false);
  const r = a.review;
  if (!r.plan && r.decisions.length === 0) return null;
  const base = `/api/tenants/${tenant.id}/assessments/${a.id}`;
  const send = (decision: string) => run(decision, () => api(`${base}/review`, json({
    decision, note: note || null, has_initiation_authority: authority,
  })).then(() => { setNote(""); setAuthority(false); }));
  const plan = r.plan;
  return (
    <div className="card">
      <h2>Review and approval</h2>
      {plan && (
        <p>
          {ROUTING_LABELS[plan.level]} risk.{" "}
          {plan.provisional.length > 0 && <>{roleList(plan.provisional, " or ")} gives a provisional approval, then </>}
          {plan.each_final_role ? roleList(plan.final) : roleList(plan.final, " or ")}{" "}
          {plan.each_final_role && plan.final.length > 1 ? "each approve, as different people." : "approves."}
          <span className="muted small"> Rule: {plan.source}.</span>
        </p>
      )}
      {r.decisions.length > 0 && (
        <ul className="plain">
          {r.decisions.map((d, i) => (
            <li key={i}>
              <span className={`badge ${d.decision === "approve" ? "good" : "warn"}`}>
                {d.decision === "approve" ? (d.step === "provisional" ? "Provisional approval" : "Approved")
                  : d.decision === "return" ? "Returned" : "Rejected"}
              </span>{" "}
              {d.name} ({ROLE_LABELS[d.role] ?? d.role}), round {d.review_round}, {new Date(d.decided_at).toLocaleString()}
              {d.has_initiation_authority && <span className="muted small"> · confirmed authority over going ahead</span>}
              {d.note && <div className="muted small">{d.note}</div>}
            </li>
          ))}
        </ul>
      )}
      {a.status === "in_review" && r.next && !r.next.done && (
        <>
          <p><strong>Next:</strong> {r.next.step === "provisional" ? "provisional approval" : "approval"} by{" "}
            {roleList(r.next.roles, r.next.step === "final" && plan?.each_final_role ? " and " : " or ")}.</p>
          {can("assessment.approve") && (
            <div className="review-box">
              {!r.can_act && (
                <p className="muted small">The policy engine decides who may act here. If you worked on this
                  assessment, or already approved it this round, you will be refused.</p>
              )}
              {r.next.step === "final" && (
                <label className="small">
                  <input type="checkbox" checked={authority} onChange={(e) => setAuthority(e.target.checked)} />{" "}
                  I have authority to take part in deciding whether the business goes ahead with this processing
                </label>
              )}
              <textarea rows={2} placeholder="Note (needed to return or reject)" value={note}
                        onChange={(e) => setNote(e.target.value)} />
              <div className="actions">
                <button disabled={!!busy} onClick={() => send("approve")}>Approve</button>
                <button disabled={!!busy} className="secondary" onClick={() => send("return")}>Return for changes</button>
                <button disabled={!!busy} className="secondary danger" onClick={() => send("reject")}>Reject</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sections
// ---------------------------------------------------------------------------

function SectionCard({ s, a, tenant, can, ratings, reload, base }: {
  s: Section; a: Assessment; tenant: Tenant; can: Can; ratings: Record<string, { inherent: Level; residual: Level | null }>;
  reload: () => void; base: string;
}) {
  const [editing, setEditing] = useState(false);
  const [history, setHistory] = useState<Revision[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const canEdit = a.editable && s.editable && can("draft.edit");

  const save = async (body: unknown) => {
    setErr(null);
    try {
      await api(`${base}/sections/${s.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body, base_revision: s.revision }),
      });
      setEditing(false);
      setHistory(null);
      reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  const toggleHistory = async () => {
    if (history) return setHistory(null);
    const h = await api<{ revisions: Revision[] }>(`${base}/sections/${s.id}/revisions`);
    setHistory(h.revisions);
  };

  return (
    <div className={`card section ${s.appendix ? "appendix" : ""}`} id={`sec-${s.id}`}>
      <div className="section-head">
        <h2>{s.appendix ? `Appendix ${s.number}` : s.number}. {s.title}</h2>
        <div className="section-meta small muted">
          {s.last_edited_by && <>
            {s.last_edited_by_type === "agent" ? <span className="badge ai">AI draft</span> : <>Edited by {s.last_edited_by}</>}
            {" · "}revision {s.revision}{" · "}
            <button className="link small" onClick={toggleHistory}>{history ? "Hide history" : "History"}</button>
          </>}
          {!s.in_regulator_report && <span className="badge">Internal only</span>}
        </div>
      </div>
      <p className="help">{s.help}</p>
      {s.what_the_law_says.length > 0 && <Law cites={s.what_the_law_says} />}
      {history && <History revs={history} />}
      {editing ? (
        <Editor s={s} a={a} onSave={save} onCancel={() => { setEditing(false); setErr(null); }} />
      ) : (
        <>
          <View s={s} a={a} ratings={ratings} tenant={tenant} can={can} reload={reload} base={base} />
          {canEdit && (s.kind !== "checklist" || s.body) && (
            <div className="actions"><button className="secondary" onClick={() => setEditing(true)}>Edit</button></div>
          )}
        </>
      )}
      {err && <p className="err">{err}</p>}
    </div>
  );
}

function Law({ cites }: { cites: LawCite[] }) {
  return (
    <details className="defs">
      <summary>What the law says ({cites.map((c) => c.citation).join("; ")})</summary>
      {cites.map((c) => (
        <div key={c.id} className="def">
          <div className="def-head">
            <a href={c.source_url} target="_blank" rel="noreferrer">{c.citation}</a>
            <span className={`badge ${c.verified ? "good" : "warn"}`}>{c.verified ? "Verified against primary text" : "Not yet verified"}</span>
          </div>
          <p>{c.summary}</p>
          <details><summary className="small">Full text</summary><blockquote>{c.text}</blockquote></details>
        </div>
      ))}
    </details>
  );
}

function History({ revs }: { revs: Revision[] }) {
  return (
    <div className="history">
      {revs.map((r) => (
        <div key={r.revision} className="rev">
          <div className="small"><strong>Revision {r.revision}</strong> by {r.author_type === "agent" ? "the OpenDPO agent" : r.author_name},{" "}
            {new Date(r.created_at).toLocaleString()}</div>
          {r.changes.text && r.revision > 1 && (
            <pre className="diff">{r.changes.text.map((l, i) => (
              <span key={i} className={l.startsWith("+") ? "add" : l.startsWith("-") ? "del" : ""}>{l}{"\n"}</span>
            ))}</pre>
          )}
          {r.revision > 1 && !r.changes.text && (
            <div className="small muted">
              {r.changes.added?.length ? `Added ${r.changes.added.join(", ")}. ` : ""}
              {r.changes.removed?.length ? `Removed ${r.changes.removed.join(", ")}. ` : ""}
              {r.changes.changed && Object.keys(r.changes.changed).length ? `Changed ${Object.keys(r.changes.changed).join(", ")}.` : ""}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Paragraphs({ text }: { text: string }) {
  return (
    <div className="prose">
      {text.trim().split("\n\n").map((block, i) => {
        const lines = block.split("\n").filter((l) => l.trim());
        const items = lines.filter((l) => l.trim().startsWith("- "));
        if (items.length && items.length === lines.length) return <ul key={i}>{items.map((l) => <li key={l}>{l.trim().slice(2)}</li>)}</ul>;
        if (items.length && items.length === lines.length - 1 && lines[0].endsWith(":")) {
          return <div key={i}><p>{lines[0]}</p><ul>{items.map((l) => <li key={l}>{l.trim().slice(2)}</li>)}</ul></div>;
        }
        return <p key={i}>{lines.join(" ")}</p>;
      })}
    </div>
  );
}

function harmName(a: Assessment, id: string | null) {
  return a.harms.entries.find((h) => h.id === id)?.name ?? id ?? "";
}

function View({ s, a, ratings, tenant, can, reload, base }: {
  s: Section; a: Assessment; ratings: Record<string, { inherent: Level; residual: Level | null }>; tenant: Tenant;
  can: Can; reload: () => void; base: string;
}) {
  const b = s.body;
  if (!b && s.kind !== "approval") return <p className="muted">Not started.</p>;
  switch (s.kind) {
    case "text":
      return <Paragraphs text={b.text} />;
    case "risk_register":
      return (
        <table className="compact">
          <thead><tr><th>Risk</th><th>What would cause it</th><th>Before</th><th>After</th><th>Cites</th></tr></thead>
          <tbody>
            {(b.risks as Risk[]).map((r) => {
              const rt = ratings[r.id];
              const accepted = a.risk_acceptances.find((x) => x.risk === r.id);
              return (
                <tr key={r.id}>
                  <td><strong>{r.id}. {r.title}</strong>{r.harm && <div className="muted small">{harmName(a, r.harm)}</div>}</td>
                  <td>{r.source_and_cause}{r.affected && <div className="muted small">Affects: {r.affected}</div>}</td>
                  <td><Lvl l={rt?.inherent} /></td>
                  <td>
                    <Lvl l={rt?.residual ?? undefined} />
                    {accepted && <div className="small ok">Accepted by {accepted.by_name}</div>}
                    {!accepted && rt?.residual && LEVELS.indexOf(rt.residual) >= LEVELS.indexOf("high") &&
                      a.editable && can("assessment.accept_risk") &&
                      <AcceptRisk tenant={tenant} base={base} risk={r.id} reload={reload} />}
                  </td>
                  <td className="small">{[...r.citations, ...r.policy_refs].join(", ")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      );
    case "safeguards":
      return (
        <table className="compact">
          <thead><tr><th>Safeguard</th><th>Addresses</th><th>Status</th><th>Owner</th></tr></thead>
          <tbody>
            {(b.safeguards as Safeguard[]).map((g) => (
              <tr key={g.id}>
                <td><strong>{g.id}. {g.title}</strong><div className="small">{g.description}</div>
                  {(g.citations.length > 0 || g.policy_refs.length > 0) &&
                    <div className="muted small">{[...g.citations, ...g.policy_refs].join(", ")}</div>}</td>
                <td>{g.addresses.join(", ")}</td>
                <td>{g.status === "in_place" ? "In place" : "Planned"}</td>
                <td>{g.owner}</td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    case "decision":
      return (
        <>
          <p><strong>{b.initiate === "yes" ? "The business will go ahead with the processing."
            : b.initiate === "no" ? "The business will not go ahead with the processing." : "Not yet decided."}</strong></p>
          {b.rationale && <Paragraphs text={b.rationale} />}
        </>
      );
    case "people":
      return <ul className="plain">{(b.people as Person[]).map((p) => <li key={p.name}>{p.name}, {p.position}{p.provided && <span className="muted"> · {p.provided}</span>}</li>)}</ul>;
    case "approval":
      return !b ? <p className="muted">Filled in when the assessment is approved.</p> : (
        <ul className="plain">
          {(b.reviewers as Reviewer[]).map((r) => (
            <li key={r.name + r.step}>{r.name}, {r.position} · {r.step === "provisional" ? "provisional approval" : "approval"} on {r.date}
              {r.has_initiation_authority && <span className="muted small"> · authority over going ahead</span>}</li>
          ))}
        </ul>
      );
    case "checklist":
      return (
        <table className="compact">
          <thead><tr><th>Item</th><th>Status</th><th>Note</th><th>Dealt with by</th></tr></thead>
          <tbody>
            {(b.items as CheckItem[]).map((i) => (
              <tr key={i.ref}>
                <td><code>{i.ref}</code></td>
                <td><span className={`badge ${i.status === "met" ? "good" : i.status === "not_met" ? "bad" : "warn"}`}>{CHECK_STATUS[i.status]}</span></td>
                <td>{i.note}</td>
                <td>{i.addresses.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    default:
      return <pre>{JSON.stringify(b, null, 2)}</pre>;
  }
}

function Lvl({ l }: { l?: Level }) {
  return l ? <span className={`lvl lv-${l}`}>{LEVEL_LABELS[l]}</span> : <span className="muted small">Not rated</span>;
}

function AcceptRisk({ tenant, base, risk, reload }: { tenant: Tenant; base: string; risk: string; reload: () => void }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [date, setDate] = useState("");
  const [err, setErr] = useState<string | null>(null);
  void tenant;
  if (!open) return <button className="link small" onClick={() => setOpen(true)}>Accept this risk</button>;
  const send = async () => {
    try {
      await api(`${base}/risk-acceptances`, json({ risk, reason, review_date: date }));
      reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  return (
    <div className="accept">
      <textarea rows={2} placeholder="Why the business accepts this risk" value={reason} onChange={(e) => setReason(e.target.value)} />
      <label className="small">Review by <input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
      <button className="small-btn" disabled={reason.trim().length < 10 || !date} onClick={send}>Record acceptance</button>
      {err && <p className="err small">{err}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Editors, one per kind of section
// ---------------------------------------------------------------------------

function Editor({ s, a, onSave, onCancel }: { s: Section; a: Assessment; onSave: (b: unknown) => void; onCancel: () => void }) {
  const [b, setB] = useState<any>(() => structuredClone(s.body ?? defaultBody(s.kind)));
  const bar = (
    <div className="actions">
      <button onClick={() => onSave(b)}>Save</button>
      <button className="secondary" onClick={onCancel}>Cancel</button>
    </div>
  );
  const levelSelect = (v: Level | null, on: (l: Level | null) => void, allowNone = false) => (
    <select value={v ?? ""} onChange={(e) => on((e.target.value || null) as Level | null)}>
      {allowNone && <option value="">Not rated</option>}
      {LEVELS.map((l) => <option key={l} value={l}>{LEVEL_LABELS[l]}</option>)}
    </select>
  );
  switch (s.kind) {
    case "text":
      return <>{<textarea rows={10} value={b.text} onChange={(e) => setB({ text: e.target.value })} />}{bar}</>;
    case "decision":
      return (
        <>
          <div className="choices">
            {[["yes", "The business will go ahead"], ["no", "The business will not go ahead"], ["undecided", "Not yet decided"]].map(([v, l]) => (
              <label key={v}><input type="radio" checked={b.initiate === v} onChange={() => setB({ ...b, initiate: v })} /> {l}</label>
            ))}
          </div>
          <textarea rows={6} value={b.rationale} onChange={(e) => setB({ ...b, rationale: e.target.value })} />
          {bar}
        </>
      );
    case "people": {
      const people: Person[] = b.people;
      const upd = (i: number, p: Partial<Person>) => setB({ people: people.map((x, j) => (j === i ? { ...x, ...p } : x)) });
      return (
        <>
          {people.map((p, i) => (
            <div key={i} className="row3">
              <input type="text" placeholder="Name" value={p.name} onChange={(e) => upd(i, { name: e.target.value })} />
              <input type="text" placeholder="Job title" value={p.position} onChange={(e) => upd(i, { position: e.target.value })} />
              <input type="text" placeholder="What they provided" value={p.provided ?? ""} onChange={(e) => upd(i, { provided: e.target.value || null })} />
              <button className="link" onClick={() => setB({ people: people.filter((_, j) => j !== i) })}>Remove</button>
            </div>
          ))}
          <button className="secondary" onClick={() => setB({ people: [...people, { name: "", position: "", provided: null }] })}>Add a person</button>
          {bar}
        </>
      );
    }
    case "risk_register": {
      const risks: Risk[] = b.risks;
      const upd = (i: number, r: Partial<Risk>) => setB({ risks: risks.map((x, j) => (j === i ? { ...x, ...r } : x)) });
      const next = `r${Math.max(0, ...risks.map((r) => Number(r.id.slice(1)))) + 1}`;
      const harms = a.harms.entries.filter((h) => h.usable);
      return (
        <>
          {risks.map((r, i) => (
            <div key={r.id} className="edit-block">
              <div className="row2">
                <input type="text" value={r.title} onChange={(e) => upd(i, { title: e.target.value })} />
                <select value={r.harm ?? ""} onChange={(e) => upd(i, { harm: e.target.value || null })}>
                  <option value="">No harm from the list</option>
                  {harms.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
                </select>
              </div>
              <textarea rows={2} placeholder="What would cause it" value={r.source_and_cause}
                        onChange={(e) => upd(i, { source_and_cause: e.target.value })} />
              <div className="ratings">
                <span>{r.id}</span>
                <label>Likelihood {levelSelect(r.likelihood, (l) => upd(i, { likelihood: l! }))}</label>
                <label>Severity {levelSelect(r.severity, (l) => upd(i, { severity: l! }))}</label>
                <label>After safeguards: likelihood {levelSelect(r.residual_likelihood, (l) => upd(i, { residual_likelihood: l }), true)}</label>
                <label>severity {levelSelect(r.residual_severity, (l) => upd(i, { residual_severity: l }), true)}</label>
                <button className="link" onClick={() => setB({ risks: risks.filter((_, j) => j !== i) })}>Remove</button>
              </div>
            </div>
          ))}
          <button className="secondary" onClick={() => setB({ risks: [...risks, {
            id: next, title: "", harm: null, source_and_cause: "", affected: null, framework_tags: [], citations: [],
            policy_refs: [], likelihood: "moderate", severity: "moderate", residual_likelihood: null, residual_severity: null,
          }] })}>Add a risk</button>
          {bar}
        </>
      );
    }
    case "safeguards": {
      const sgs: Safeguard[] = b.safeguards;
      const riskIds: string[] = (sectionBody(a, "risks")?.risks ?? []).map((r: Risk) => r.id);
      const upd = (i: number, g: Partial<Safeguard>) => setB({ safeguards: sgs.map((x, j) => (j === i ? { ...x, ...g } : x)) });
      const next = `s${Math.max(0, ...sgs.map((g) => Number(g.id.slice(1)))) + 1}`;
      return (
        <>
          {sgs.map((g, i) => (
            <div key={g.id} className="edit-block">
              <div className="row2">
                <input type="text" value={g.title} onChange={(e) => upd(i, { title: e.target.value })} />
                <input type="text" placeholder="Owner (a role)" value={g.owner ?? ""} onChange={(e) => upd(i, { owner: e.target.value || null })} />
              </div>
              <textarea rows={2} value={g.description} onChange={(e) => upd(i, { description: e.target.value })} />
              <div className="ratings">
                <span>{g.id}</span>
                <select value={g.status} onChange={(e) => upd(i, { status: e.target.value as Safeguard["status"] })}>
                  <option value="planned">Planned</option><option value="in_place">In place</option>
                </select>
                <span className="small">Addresses:</span>
                {riskIds.map((rid) => (
                  <label key={rid} className="small">
                    <input type="checkbox" checked={g.addresses.includes(rid)}
                           onChange={(e) => upd(i, { addresses: e.target.checked ? [...g.addresses, rid] : g.addresses.filter((x) => x !== rid) })} />{rid}
                  </label>
                ))}
                <button className="link" onClick={() => setB({ safeguards: sgs.filter((_, j) => j !== i) })}>Remove</button>
              </div>
            </div>
          ))}
          <button className="secondary" onClick={() => setB({ safeguards: [...sgs, {
            id: next, title: "", description: "", status: "planned", owner: null, addresses: [], citations: [], policy_refs: [],
          }] })}>Add a safeguard</button>
          {bar}
        </>
      );
    }
    case "checklist": {
      const items: CheckItem[] = b.items;
      const upd = (i: number, c: Partial<CheckItem>) => setB({ items: items.map((x, j) => (j === i ? { ...x, ...c } : x)) });
      return (
        <>
          {items.map((it, i) => (
            <div key={it.ref} className="row3">
              <code>{it.ref}</code>
              <select value={it.status} onChange={(e) => upd(i, { status: e.target.value })}>
                {Object.entries(CHECK_STATUS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <input type="text" value={it.note} onChange={(e) => upd(i, { note: e.target.value })} />
            </div>
          ))}
          {bar}
        </>
      );
    }
    default:
      return <p className="muted">This section is filled in by the approval steps.</p>;
  }
}

function defaultBody(kind: string): unknown {
  return ({ text: { text: "" }, risk_register: { risks: [] }, safeguards: { safeguards: [] }, people: { people: [] },
            decision: { initiate: "undecided", rationale: "" }, checklist: { items: [] } } as Record<string, unknown>)[kind];
}
