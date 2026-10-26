import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./auth";
import {
  Answers, Change, Citation, Definition, Explained, IntakeForm, ProjectDetail, ProjectRow, Property,
  STATUS_LABELS, humanize, visibleIds,
} from "./intake";
import { Tenant } from "./types";

type Can = (a: string) => boolean;

export function Projects({ tenant, can }: { tenant: Tenant; can: Can }) {
  const [open, setOpen] = useState<string | "new" | null>(null);
  const [rows, setRows] = useState<ProjectRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    api<ProjectRow[]>(`/api/tenants/${tenant.id}/projects`).then(setRows).catch((e: Error) => setErr(e.message));
  }, [tenant.id]);
  useEffect(load, [load]);

  if (open === "new") {
    return <IntakeEditor tenant={tenant} onDone={(id) => { load(); setOpen(id); }} onCancel={() => setOpen(null)} />;
  }
  if (open) {
    return <ProjectView tenant={tenant} can={can} id={open} onBack={() => { load(); setOpen(null); }} />;
  }
  return (
    <section>
      <h1>Projects</h1>
      <p className="muted">Every assessment starts from one intake. Rules, not the model, decide what it triggers.</p>
      {can("intake.submit") && (
        <div className="actions"><button onClick={() => setOpen("new")}>Start an intake</button></div>
      )}
      {err && <p className="err">{err}</p>}
      {rows.length === 0 ? <p className="muted">No projects yet.</p> : (
        <table>
          <thead><tr><th>Project</th><th>Status</th><th>Version</th><th>Started by</th><th>Updated</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="clickable" onClick={() => setOpen(r.id)}>
                <td><button className="link" onClick={() => setOpen(r.id)}>{r.name}</button></td>
                <td><span className={`status ${r.status}`}>{STATUS_LABELS[r.status]}</span></td>
                <td>{r.version ?? "Not submitted"}</td>
                <td>{r.created_by_name}</td>
                <td>{new Date(r.updated_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// The intake form
// ---------------------------------------------------------------------------

function useForm(tenantId: string) {
  const [form, setForm] = useState<IntakeForm | null>(null);
  useEffect(() => {
    api<IntakeForm>(`/api/tenants/${tenantId}/intake/form`).then(setForm);
  }, [tenantId]);
  return form;
}

function IntakeEditor({ tenant, id, initial, onDone, onCancel }: {
  tenant: Tenant; id?: string; initial?: Answers; onDone: (id: string) => void; onCancel: () => void;
}) {
  const form = useForm(tenant.id);
  const [answers, setAnswers] = useState<Answers>(initial ?? {});
  const [projectId, setProjectId] = useState<string | undefined>(id);
  const [problems, setProblems] = useState<{ question: string; problem: string }[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const shown = useMemo(() => (form ? new Set(visibleIds(form, answers)) : new Set<string>()), [form, answers]);
  if (!form) return <p className="loading">Loading the form…</p>;
  const props = form.schema.properties;

  const set = (qid: string, v: unknown) => {
    setAnswers((a) => {
      const next = { ...a, [qid]: v };
      // Sensitive data categories pre-answer the sensitive personal information question; the submitter confirms.
      const sens = props[qid]?.["x-opendpo"].sensitive_options;
      if (sens && Array.isArray(v) && !("data.sensitive" in a)) {
        if (v.some((x) => sens.includes(x as string))) next["data.sensitive"] = true;
      }
      return next;
    });
  };

  const save = async (): Promise<string> => {
    if (projectId) {
      const r = await api<{ problems: typeof problems }>(`/api/tenants/${tenant.id}/projects/${projectId}/answers`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers }),
      });
      setProblems(r.problems);
      return projectId;
    }
    const r = await api<{ id: string }>(`/api/tenants/${tenant.id}/projects`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers }),
    });
    setProjectId(r.id);
    return r.id;
  };

  const run = async (submit: boolean) => {
    setBusy(true);
    setMsg(null);
    try {
      const pid = await save();
      if (!submit) {
        setMsg("Saved. Nothing is triaged until you submit.");
        return;
      }
      try {
        await api(`/api/tenants/${tenant.id}/projects/${pid}/submit`, { method: "POST" });
        onDone(pid);
      } catch (e) {
        setMsg((e as Error).message);
        const r = await api<{ problems: typeof problems }>(`/api/tenants/${tenant.id}/projects/${pid}/answers`, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers }),
        });
        setProblems(r.problems);
      }
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const problemFor = (qid: string) => problems.find((p) => p.question === qid);
  const sections = form.schema["x-opendpo-sections"];

  return (
    <section>
      <button className="link" onClick={onCancel}>← Back</button>
      <h1>{(answers["project.name"] as string) || "New intake"}</h1>
      <p className="muted">
        Answer what you know. Sections for a law appear only when your answers make it relevant. Questions that
        decide a legal outcome show the law's own definition beside them.
      </p>
      {sections.map((s) => {
        const qs = Object.keys(props).filter((q) => props[q]["x-opendpo"].section === s.id && shown.has(q));
        if (qs.length === 0) return null;
        const unverified = s.rules_total !== undefined && s.rules_usable !== s.rules_total;
        return (
          <div className="card" key={s.id}>
            <h2>{s.title}</h2>
            {unverified && (
              <p className="note">
                {s.rules_usable} of {s.rules_total} rules for this law are verified. Answers are recorded, but rules
                waiting for verification do not run.
              </p>
            )}
            {qs.map((q) => (
              <Question key={q} id={q} prop={props[q]} value={answers[q]} onChange={(v) => set(q, v)}
                        problem={problemFor(q)?.problem} />
            ))}
          </div>
        );
      })}
      {Object.keys(form.scoping).length > 0 && (
        <p className="muted small">
          Scoping answers for {tenant.name} are already on file and are applied to every intake.
        </p>
      )}
      {problems.length > 0 && <p className="err">{problems.length} question(s) still need an answer or a fix.</p>}
      {msg && <p className={msg.startsWith("Saved") ? "ok" : "err"}>{msg}</p>}
      <div className="actions">
        <button disabled={busy} onClick={() => run(true)}>Submit for triage</button>
        <button disabled={busy} className="secondary" onClick={() => run(false)}>Save draft</button>
      </div>
    </section>
  );
}

function Question({ id, prop, value, onChange, problem }: {
  id: string; prop: Property; value: unknown; onChange: (v: unknown) => void; problem?: string;
}) {
  const meta = prop["x-opendpo"];
  const choices = prop.oneOf ?? prop.items?.oneOf ?? [];
  let input: JSX.Element;
  switch (meta.type) {
    case "textarea":
      input = <textarea rows={5} placeholder={meta.placeholder} value={(value as string) ?? ""}
                        onChange={(e) => onChange(e.target.value)} />;
      break;
    case "date":
      input = <input type="date" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />;
      break;
    case "boolean":
      input = (
        <div className="choices inline">
          {[true, false].map((b) => (
            <label key={String(b)}>
              <input type="radio" name={id} checked={value === b} onChange={() => onChange(b)} /> {b ? "Yes" : "No"}
            </label>
          ))}
        </div>
      );
      break;
    case "choice":
      input = (
        <div className="choices">
          {choices.map((c) => (
            <label key={c.const}>
              <input type="radio" name={id} checked={value === c.const} onChange={() => onChange(c.const)} /> {c.title}
            </label>
          ))}
        </div>
      );
      break;
    case "multichoice": {
      const list = Array.isArray(value) ? (value as string[]) : [];
      input = (
        <div className="choices">
          {choices.map((c) => (
            <label key={c.const}>
              <input type="checkbox" checked={list.includes(c.const)}
                     onChange={(e) => onChange(e.target.checked ? [...list, c.const] : list.filter((x) => x !== c.const))} />
              {" "}{c.title}
            </label>
          ))}
          {list.length === 0 && <span className="muted small">Leave all unticked if none apply.</span>}
        </div>
      );
      break;
    }
    default:
      input = <input type="text" value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />;
  }
  return (
    <div className={`question ${problem ? "has-problem" : ""}`}>
      <label className="q" htmlFor={id}>{prop.title}</label>
      {prop.description && <p className="help">{prop.description}</p>}
      {input}
      {problem && <p className="err small">{problem}</p>}
      {meta.definitions && meta.definitions.length > 0 && <Definitions defs={meta.definitions} />}
    </div>
  );
}

function Definitions({ defs }: { defs: Definition[] }) {
  return (
    <details className="defs">
      <summary>What the law says ({defs.map((d) => d.citation).join("; ")})</summary>
      {defs.map((d) => (
        <div key={d.id} className="def">
          <div className="def-head">
            <a href={d.source_url} target="_blank" rel="noreferrer">{d.citation}</a>
            <span className={`badge ${d.verified ? "good" : "warn"}`}>
              {d.verified ? "Verified against primary text" : "Not yet verified"}
            </span>
          </div>
          <p>{d.summary}</p>
          <details>
            <summary className="small">Full text{d.location ? ` (${d.location})` : ""}</summary>
            <blockquote>{d.text}</blockquote>
          </details>
        </div>
      ))}
    </details>
  );
}

// ---------------------------------------------------------------------------
// A project: its status, the triage result and the analyst's decision
// ---------------------------------------------------------------------------

function ProjectView({ tenant, can, id, onBack }: { tenant: Tenant; can: Can; id: string; onBack: () => void }) {
  const [p, setP] = useState<ProjectDetail | null>(null);
  const [editing, setEditing] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    api<ProjectDetail>(`/api/tenants/${tenant.id}/projects/${id}`).then(setP).catch((e: Error) => setErr(e.message));
  }, [tenant.id, id]);
  useEffect(load, [load]);

  if (err) return <p className="err">{err}</p>;
  if (!p) return <p className="loading">Loading…</p>;
  if (editing) {
    return <IntakeEditor tenant={tenant} id={p.id} initial={p.answers}
                         onDone={() => { setEditing(false); load(); }} onCancel={() => { setEditing(false); load(); }} />;
  }
  const latest = p.submissions[0];
  return (
    <section>
      <button className="link" onClick={onBack}>← All projects</button>
      <h1>{p.name}</h1>
      <p className="muted">
        <span className={`status ${p.status}`}>{STATUS_LABELS[p.status]}</span>
        {latest && <> · version {latest.version}, submitted by {latest.submitted_by_name} on{" "}
          {new Date(latest.submitted_at).toLocaleString()}</>}
      </p>
      {p.status !== "confirmed" && can("intake.submit") && (
        <div className="actions"><button className="secondary" onClick={() => setEditing(true)}>
          {p.status === "draft" ? "Continue the intake" : "Change answers and resubmit"}
        </button></div>
      )}
      {p.status === "awaiting_clarification" && <Clarification tenant={tenant} p={p} can={can} reload={load} />}
      {p.triage && p.triage.status !== "superseded" && (
        <Triage tenant={tenant} p={p} can={can} reload={load} />
      )}
    </section>
  );
}

function Clarification({ tenant, p, can, reload }: { tenant: Tenant; p: ProjectDetail; can: Can; reload: () => void }) {
  const [q, setQ] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const send = async () => {
    try {
      await api(`/api/tenants/${tenant.id}/projects/${p.id}/clarification`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q }),
      });
      setQ("");
      reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  return (
    <div className="card warn">
      <h2>Waiting for an analyst</h2>
      <p>The submitter is not sure whether the project uses AI, so triage waits until an analyst follows up.</p>
      {p.clarification && <p><strong>Analyst's question:</strong> {p.clarification}</p>}
      {can("intake.clarify") && (
        <>
          <textarea rows={3} placeholder="Ask the submitter what you need to settle the AI question"
                    value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="actions"><button disabled={q.trim().length < 3} onClick={send}>Send question</button></div>
        </>
      )}
      {err && <p className="err">{err}</p>}
    </div>
  );
}

function Triage({ tenant, p, can, reload }: { tenant: Tenant; p: ProjectDetail; can: Can; reload: () => void }) {
  const t = p.triage!;
  const r = t.result;
  const removed = new Set((t.decision?.changes ?? []).filter((c) => c.action === "remove").map((c) => c.rule));
  return (
    <>
      <div className="card">
        <h2>Triage result</h2>
        <p className="muted small">
          Decided by verified rules in the policy engine from version {t.submission_version} of the intake, on{" "}
          {new Date(t.created_at).toLocaleString()}. Content: {Object.entries(r.content_versions)
            .map(([k, v]) => `${k} ${v}`).join(", ")}.
        </p>
        <h3>Assessments required</h3>
        {r.assessments.length === 0 ? <p className="muted">None triggered.</p> : r.assessments.map((a) => (
          <div key={a.assessment} className="result">
            <div className="result-head"><strong>{humanize(a.assessment)}</strong></div>
            {a.triggered_by.map((e) => <Rule key={e.rule} e={e} struck={removed.has(e.rule)} />)}
          </div>
        ))}
        <h3>Obligations</h3>
        {r.obligations.length === 0 ? <p className="muted">None triggered.</p>
          : r.obligations.map((e) => <Rule key={e.rule} e={e} struck={removed.has(e.rule)} />)}
        <details>
          <summary>How the rules classified the system ({r.classifications.length})</summary>
          {r.classifications.map((e) => <Rule key={e.rule} e={e} struck={removed.has(e.rule)} />)}
        </details>
        {r.not_run.length > 0 && (
          <details>
            <summary className="warn-text">{r.not_run.length} rules were not run because they are not yet verified</summary>
            <ul className="small">
              {r.not_run.map((n) => <li key={n.rule}><code>{n.rule}</code> {n.title}</li>)}
            </ul>
          </details>
        )}
      </div>
      {t.status === "confirmed" && t.decision ? <DecisionShown t={t} />
        : can("triage.confirm") ? <DecisionPanel tenant={tenant} p={p} reload={reload} />
        : <p className="muted">Waiting for a privacy analyst to confirm or change this result.</p>}
    </>
  );
}

function Rule({ e, struck }: { e: Explained; struck?: boolean }) {
  const extra = Object.entries(e.result).filter(([k]) => !["obligation", "assessment", "set_fact", "value", "trigger"]
    .includes(k));
  return (
    <div className={`rule ${struck ? "struck" : ""}`}>
      <div className="rule-head">
        <strong>{e.title}</strong> <code className="small">{e.rule}</code>
        {struck && <span className="badge warn">Set aside by the analyst</span>}
      </div>
      <p>{e.explanation}</p>
      {extra.length > 0 && (
        <p className="small muted">{extra.map(([k, v]) => `${k.replace(/_/g, " ")}: ${String(v)}`).join(" · ")}</p>
      )}
      <Citations cs={e.citations} />
    </div>
  );
}

function Citations({ cs }: { cs: Citation[] }) {
  return (
    <details className="cites">
      <summary className="small">Citations ({cs.length})</summary>
      <ul>
        {cs.map((c) => (
          <li key={c.id}>
            <a href={c.source_url} target="_blank" rel="noreferrer">{c.citation}</a>
            {c.location && <span className="muted small"> ({c.location})</span>}: {c.summary}
          </li>
        ))}
      </ul>
    </details>
  );
}

function DecisionShown({ t }: { t: NonNullable<ProjectDetail["triage"]> }) {
  const d = t.decision!;
  return (
    <div className="card good-soft">
      <h2>{d.decision === "confirm" ? "Confirmed as the rules decided" : "Confirmed with changes"}</h2>
      <p className="muted small">By {t.decided_by_name} on {new Date(t.decided_at!).toLocaleString()}.</p>
      {d.changes.length > 0 && (
        <ul>
          {d.changes.map((c, i) => (
            <li key={i}>
              {c.action === "add" ? <>Added <strong>{c.item}</strong></> : <>Set aside <code>{c.rule}</code></>}: {c.reason}
            </li>
          ))}
        </ul>
      )}
      {d.note && <p>{d.note}</p>}
    </div>
  );
}

function DecisionPanel({ tenant, p, reload }: { tenant: Tenant; p: ProjectDetail; reload: () => void }) {
  const t = p.triage!;
  const [changes, setChanges] = useState<Change[]>([]);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const results = [...t.result.assessments.flatMap((a) => a.triggered_by), ...t.result.obligations];

  const send = async (decision: "confirm" | "change") => {
    try {
      await api(`/api/tenants/${tenant.id}/projects/${p.id}/triage/${t.id}/decision`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, changes: decision === "change" ? changes : [], note: note || null }),
      });
      reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  };
  const update = (i: number, c: Partial<Change>) => setChanges((cs) => cs.map((x, j) => (j === i ? { ...x, ...c } : x)));
  const valid = changes.every((c) => c.reason.trim().length >= 3 && (c.action === "add" ? !!c.item?.trim() : !!c.rule));

  return (
    <div className="card">
      <h2>Analyst confirmation</h2>
      <p className="muted">
        Confirm the result, or change it. Changes are recorded beside the rules' result, each with its reason; the
        rules' result itself is never edited.
      </p>
      {changes.map((c, i) => (
        <div key={i} className="change">
          {c.action === "remove" ? (
            <select value={c.rule ?? ""} onChange={(e) => update(i, { rule: e.target.value })}>
              <option value="">Set aside which result?</option>
              {results.map((e) => <option key={e.rule} value={e.rule}>{e.title} ({e.rule})</option>)}
            </select>
          ) : (
            <input type="text" placeholder="What to add, for example: EU AI Act check" value={c.item ?? ""}
                   onChange={(e) => update(i, { item: e.target.value })} />
          )}
          <input type="text" placeholder="Reason" value={c.reason} onChange={(e) => update(i, { reason: e.target.value })} />
          <button className="link" onClick={() => setChanges((cs) => cs.filter((_, j) => j !== i))}>Remove</button>
        </div>
      ))}
      <div className="actions">
        <button className="secondary" onClick={() => setChanges((cs) => [...cs, { action: "add", item: "", reason: "" }])}>
          Add an item
        </button>
        <button className="secondary" onClick={() => setChanges((cs) => [...cs, { action: "remove", rule: "", reason: "" }])}>
          Set aside a result
        </button>
      </div>
      <textarea rows={2} placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="actions">
        {changes.length === 0
          ? <button onClick={() => send("confirm")}>Confirm as is</button>
          : <button disabled={!valid} onClick={() => send("change")}>Confirm with these changes</button>}
      </div>
      {err && <p className="err">{err}</p>}
    </div>
  );
}
