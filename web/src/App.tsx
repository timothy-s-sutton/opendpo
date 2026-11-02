import { useCallback, useEffect, useState } from "react";
import { api, keycloak } from "./auth";
import { InventoryPage } from "./Inventory";
import { Projects, Target } from "./Projects";
import { AuditEvent, Me, ROLE_LABELS, Tenant, Verification } from "./types";

type Page = "overview" | "projects" | "inventory" | "audit" | "members";

const ACTION_LABELS: Record<string, string> = {
  "intake.submit": "Submit a project for review",
  "intake.read": "See projects and their triage results",
  "intake.clarify": "Follow up on unclear intake answers",
  "triage.confirm": "Confirm triage results",
  "draft.edit": "Edit assessment drafts",
  "assessment.read": "Read assessments",
  "assessment.submit": "Submit assessments for review",
  "assessment.approve": "Approve assessments (subject to segregation of duties)",
  "assessment.accept_risk": "Accept risks that stay high after safeguards",
  "assessment.export": "Export assessments",
  "inventory.read": "Read the data inventory",
  "policy.read": "Read the organization's policies",
  "members.read": "See who holds which role",
  "tenant.ack_intended_use": "Acknowledge the intended-use notice",
  "audit.read": "Read the audit log",
  "audit.verify": "Verify the audit chain",
  "audit.export": "Export the audit log",
};

export function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [page, setPage] = useState<Page>("overview");
  const [error, setError] = useState<string | null>(null);
  const [target, setTarget] = useState<Target | null>(null);
  const go = (p: Page) => { setTarget(null); setPage(p); };
  const openTask = (t: Target) => { setTarget(t); setPage("projects"); };

  const loadTenant = useCallback(async (id: string) => {
    setTenant(await api<Tenant>(`/api/tenants/${id}`));
  }, []);

  useEffect(() => {
    api<Me>("/api/me")
      .then((m) => {
        setMe(m);
        if (m.tenants[0]) return loadTenant(m.tenants[0].id);
      })
      .catch((e: Error) => setError(e.message));
  }, [loadTenant]);

  if (error) return <div className="boot-error">{error}</div>;
  if (!me) return <div className="loading">Loading…</div>;

  const roles = tenant ? [...tenant.my_roles, ...tenant.my_workspace_roles] : [];
  const can = (a: string) => tenant?.allowed_actions.includes(a) ?? false;

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">OpenDPO</div>
        {me.tenants.length > 1 ? (
          <select value={tenant?.id} onChange={(e) => loadTenant(e.target.value)}>
            {me.tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        ) : (
          <div className="tenant">{tenant?.name ?? "No tenant"}</div>
        )}
        <div className="user">
          <span>{me.display_name}</span>
          {roles.map((r) => <span key={r} className="role">{ROLE_LABELS[r] ?? r}</span>)}
          <button className="link" onClick={() => keycloak.logout({ redirectUri: window.location.origin })}>
            Sign out
          </button>
        </div>
      </header>

      <nav className="tabs">
        <button className={page === "overview" ? "on" : ""} onClick={() => go("overview")}>Overview</button>
        {can("intake.read") && (
          <button className={page === "projects" ? "on" : ""} onClick={() => go("projects")}>Projects</button>
        )}
        {can("inventory.read") && (
          <button className={page === "inventory" ? "on" : ""} onClick={() => go("inventory")}>Inventory</button>
        )}
        {can("audit.read") && (
          <button className={page === "audit" ? "on" : ""} onClick={() => go("audit")}>Audit log</button>
        )}
        {can("members.read") && (
          <button className={page === "members" ? "on" : ""} onClick={() => go("members")}>Members</button>
        )}
      </nav>

      <main>
        {!tenant && <p>You have no tenant memberships yet.</p>}
        {tenant && page === "overview" && <Overview tenant={tenant} can={can} reload={() => loadTenant(tenant.id)} onOpen={openTask} />}
        {tenant && page === "projects" && <Projects key={`${tenant.id}:${target?.project ?? ""}:${target?.assessment ?? ""}`} tenant={tenant} can={can}
                                                     target={target} />}
        {tenant && page === "inventory" && <InventoryPage key={tenant.id} tenant={tenant} />}
        {tenant && page === "audit" && <AuditLog tenant={tenant} can={can} />}
        {tenant && page === "members" && <Members tenant={tenant} />}
      </main>

      <footer className="notice">
        OpenDPO is a proof of concept. It provides no legal advice and does not replace review by qualified
        privacy, legal and compliance professionals. All data shown is fictional.
      </footer>
    </div>
  );
}

type Task = { project_id: string; project_name: string; assessment_id: string | null; detail: string | null;
              since: string | null };
type TaskList = { groups: { id: string; title: string; items: Task[] }[]; count: number };

// Work waiting on the signed-in person. The API decides what counts, with the same checks as
// the pages where the work is done.
function Tasks({ tenant, onOpen }: { tenant: Tenant; onOpen: (t: Target) => void }) {
  const [t, setT] = useState<TaskList | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api<TaskList>(`/api/tenants/${tenant.id}/tasks`).then(setT).catch((e: Error) => setErr(e.message));
  }, [tenant.id]);
  return (
    <div className="card tasks">
      <h2>Tasks{t && t.count > 0 && <span className="count">{t.count}</span>}</h2>
      {err && <p className="err">{err}</p>}
      {!t && !err && <p className="muted">Loading…</p>}
      {t && t.count === 0 && <p className="muted">Nothing needs your action right now.</p>}
      {t?.groups.map((g) => (
        <div key={g.id} className="task-group">
          <h3>{g.title}</h3>
          <ul className="task-list">
            {g.items.map((i) => (
              <li key={(i.assessment_id ?? i.project_id) + g.id}>
                <button className="link" onClick={() => onOpen({ project: i.project_id, assessment: i.assessment_id })}>
                  {i.project_name}
                </button>
                {(i.detail || i.since) && (
                  <div className="muted small">
                    {i.detail}{i.detail && i.since ? " · " : ""}{i.since && new Date(i.since).toLocaleDateString()}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function Overview({ tenant, can, reload, onOpen }: {
  tenant: Tenant; can: (a: string) => boolean; reload: () => void; onOpen: (t: Target) => void;
}) {
  const [msg, setMsg] = useState<string | null>(null);
  const ack = async () => {
    try {
      await api(`/api/tenants/${tenant.id}/intended-use/ack`, { method: "POST" });
      reload();
    } catch (e) {
      setMsg((e as Error).message);
    }
  };
  return (
    <section>
      <h1>{tenant.name}</h1>
      <p className="muted">Approval preset: {tenant.approval_preset.replace("_", " ")}</p>

      <Tasks tenant={tenant} onOpen={onOpen} />

      <div className={`card ${tenant.intended_use_acknowledged ? "" : "warn"}`}>
        <h2>Intended-use notice</h2>
        <p>
          OpenDPO drafts and explains; qualified people decide. Outputs are drafts for review, not legal advice.
        </p>
        {tenant.intended_use_acknowledged ? (
          <p className="ok">Acknowledged {new Date(tenant.intended_use_ack_at!).toLocaleString()}, recorded in the audit log.</p>
        ) : can("tenant.ack_intended_use") ? (
          <button onClick={ack}>Acknowledge for this tenant</button>
        ) : (
          <p>Waiting for a tenant admin to acknowledge.</p>
        )}
        {msg && <p className="err">{msg}</p>}
      </div>

      <div className="card">
        <h2>What your role allows here</h2>
        <p className="muted">Decided by the policy engine (Open Policy Agent), not by this page.</p>
        <ul className="checks">
          {Object.entries(ACTION_LABELS).map(([a, label]) => (
            <li key={a} className={can(a) ? "yes" : "no"}>{label}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function AuditLog({ tenant, can }: { tenant: Tenant; can: (a: string) => boolean }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [result, setResult] = useState<Verification | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    api<AuditEvent[]>(`/api/tenants/${tenant.id}/audit`).then(setEvents).catch((e: Error) => setErr(e.message));
  }, [tenant.id]);
  useEffect(load, [load]);

  const verify = async () => {
    setResult(await api<Verification>(`/api/tenants/${tenant.id}/audit/verify`, { method: "POST" }));
    load();
  };
  const exportJson = async () => {
    try {
      const data = await api<unknown>(`/api/tenants/${tenant.id}/audit/export`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `opendpo-audit-${tenant.name.replace(/\s+/g, "-").toLowerCase()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      load();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  return (
    <section>
      <h1>Audit log</h1>
      <p className="muted">
        Append-only. Each event stores the hash of the one before it, so any edit or deletion breaks the chain.
      </p>
      <div className="actions">
        {can("audit.verify") && <button onClick={verify}>Verify chain</button>}
        {can("audit.export") && <button className="secondary" onClick={exportJson}>Export JSON</button>}
      </div>
      {result && (
        <div className={`card ${result.ok ? "good" : "bad"}`}>
          {result.ok
            ? `Chain intact: ${result.events_checked} events verified.`
            : `Chain broken at event ${result.first_broken_seq}: ${result.problem}.`}
        </div>
      )}
      {err && <p className="err">{err}</p>}
      <table>
        <thead>
          <tr><th>#</th><th>When</th><th>Who</th><th>Action</th><th>Detail</th><th>Hash</th></tr>
        </thead>
        <tbody>
          {events.map((e) => (
            <tr key={e.seq}>
              <td>{e.seq}</td>
              <td>{new Date(e.occurred_at).toLocaleString()}</td>
              <td>
                {e.actor_name}
                <div className="muted small">{e.actor_roles.map((r) => ROLE_LABELS[r] ?? r).join(", ")}</div>
              </td>
              <td><code>{e.action}</code></td>
              <td className="small">{summarize(e)}</td>
              <td><code title={`prev ${e.prev_hash}`}>{e.hash.slice(0, 12)}…</code></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function summarize(e: AuditEvent): string {
  const p = e.payload as Record<string, unknown>;
  if (e.action === "access.denied") return `Tried ${p.attempted}: ${(p.reasons as string[]).join("; ")}`;
  if (e.action === "audit.verified") return p.ok ? `Intact (${p.events_checked} events)` : `Broken at ${p.first_broken_seq}`;
  if (e.action === "audit.exported") return `${p.events} events exported`;
  return "";
}

function Members({ tenant }: { tenant: Tenant }) {
  const [rows, setRows] = useState<{ id: string; display_name: string; role: string }[]>([]);
  useEffect(() => {
    api<typeof rows>(`/api/tenants/${tenant.id}/members`).then(setRows);
  }, [tenant.id]);
  return (
    <section>
      <h1>Members</h1>
      <p className="muted">Roles belong to memberships, so one person can hold different roles for different clients.</p>
      <table>
        <thead><tr><th>Person</th><th>Role</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.id}-${r.role}`}><td>{r.display_name}</td><td>{ROLE_LABELS[r.role] ?? r.role}</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
