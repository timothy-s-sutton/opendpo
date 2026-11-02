import { useEffect, useState } from "react";
import { api } from "./auth";
import { Tenant } from "./types";

// The inventory record of a processing activity (INV-01): what the organization already knows
// about the system, its data and who receives it. The agent drafts from this record and the
// intake answers, so showing it lets a reader see where every fact in a draft came from.

type Vendor = { name: string; role: string; dpa_status: string; notes: string | null; purpose?: string };
export type ActivityRecord = {
  id: string; name: string; purpose: string; decision_domain: string | null; ai_role: string | null;
  human_review: string | null; human_review_note: string | null;
  people_affected: Record<string, Record<string, number>>; collection: string | null;
  consumer_interaction: string | null; disclosures: string | null; go_live: string | null; stage: string | null;
  systems: { name: string; business_owner: string; technical_owner: string | null; vendor_name: string | null;
             hosting: string | null; status: string }[];
  ai_components: { name: string; version: string | null; vendor_name: string | null; kind: string; intended_use: string;
                   inputs: string; output: string; trained_on_personal_data: boolean; known_limitations: string | null }[];
  data_categories: { name: string; examples: string | null; sensitive: boolean; ccpa_category: string | null;
                     retention: string; why_needed: string | null }[];
  subject_groups: { name: string; approximate_count: number | null }[];
  recipients: Vendor[];
};

const PLACES: Record<string, string> = {
  "US-CA": "California", "US-CO": "Colorado", "US-NYC": "New York City", "US-other": "Other states",
};
const REVIEW: Record<string, string> = {
  none: "None", limited: "Limited (a person looks, but not every part of meaningful review is met)",
  meaningful: "Meaningful (understands the output, weighs other information, can change the outcome)",
};
const ROLE: Record<string, string> = {
  none: "None", assists: "Assists a person", materially_influences: "Materially influences the decision",
  decides: "Makes the decision",
};
const human = (s: string | null) => (s ? s.replace(/_/g, " ") : "Not recorded");

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="labelled"><div className="lbl">{label}</div><div className="field-body">{children}</div></div>;
}

export function InventoryRecord({ r }: { r: ActivityRecord }) {
  return (
    <div className="prose inventory">
      <Field label="Purpose">{r.purpose}</Field>
      <Field label="Stage and go-live">{human(r.stage)}{r.go_live && `, going live ${r.go_live}`}</Field>
      <Field label="How AI takes part">{ROLE[r.ai_role ?? ""] ?? human(r.ai_role)}</Field>
      <Field label="Human review">
        {REVIEW[r.human_review ?? ""] ?? human(r.human_review)}
        {r.human_review_note && <div className="muted">{r.human_review_note}</div>}
      </Field>
      <Field label="Systems">
        <ul className="items">{r.systems.map((s) => (
          <li key={s.name}><strong>{s.name}</strong>
            <div className="sub">Owner: {s.business_owner}{s.technical_owner && `; technical owner: ${s.technical_owner}`}
              {s.vendor_name && `; vendor: ${s.vendor_name}`}; {human(s.status)}</div></li>
        ))}</ul>
      </Field>
      {r.ai_components.map((c) => (
        <Field key={c.name} label={`AI model: ${c.name}${c.version ? ` ${c.version}` : ""}`}>
          <ul className="items">
            <li><strong>What it does</strong><div className="sub">{c.intended_use}</div></li>
            <li><strong>Inputs</strong><div className="sub">{c.inputs}</div></li>
            <li><strong>Output</strong><div className="sub">{c.output}</div></li>
            {c.known_limitations && <li><strong>Known limits</strong><div className="sub">{c.known_limitations}</div></li>}
            <li><strong>Trained on personal data</strong><div className="sub">{c.trained_on_personal_data ? "Yes" : "No"}</div></li>
          </ul>
        </Field>
      ))}
      <Field label="Personal information">
        <ul className="items">{r.data_categories.map((d) => (
          <li key={d.name}><strong>{d.name}{d.examples && ` (${d.examples})`}</strong>
            <div className="sub">{d.why_needed}{d.why_needed && " "}Kept: {d.retention}{d.sensitive && " · sensitive"}</div></li>
        ))}</ul>
      </Field>
      <Field label="People affected">
        <ul className="items">{Object.entries(r.people_affected).map(([group, places]) => (
          <li key={group}><strong>{human(group)}</strong>
            <div className="sub">{Object.entries(places).map(([k, n]) => `${PLACES[k] ?? k}: ${n.toLocaleString()}`).join(" · ")}</div></li>
        ))}</ul>
      </Field>
      {r.collection && <Field label="How information is collected">{r.collection}</Field>}
      {r.consumer_interaction && <Field label="How people interact with the business">{r.consumer_interaction}</Field>}
      {r.disclosures && <Field label="What people are told">{r.disclosures}</Field>}
      <Field label="Who receives the information">
        <ul className="items">{r.recipients.map((v) => (
          <li key={v.name}><strong>{v.name} ({human(v.role)})</strong>
            <div className="sub">{v.purpose}{v.notes && <div className="muted">{v.notes}</div>}</div></li>
        ))}</ul>
      </Field>
    </div>
  );
}

// Shown on the assessment page: open before the draft exists, collapsed after.
export function InventoryPanel({ tenant, activityId, startOpen }: { tenant: Tenant; activityId: string; startOpen: boolean }) {
  const [r, setR] = useState<ActivityRecord | null>(null);
  useEffect(() => {
    api<ActivityRecord>(`/api/tenants/${tenant.id}/inventory/activities/${activityId}`).then(setR).catch(() => setR(null));
  }, [tenant.id, activityId]);
  if (!r) return null;
  return (
    <details className="card inventory-panel" open={startOpen}>
      <summary className="section-head">
        <h2>Inventory record: {r.name}</h2>
        <span className="muted">What the organization already knows. The draft uses this and the intake answers.</span>
      </summary>
      <InventoryRecord r={r} />
    </details>
  );
}

// The Inventory tab: read-only for the preview.
export function InventoryPage({ tenant }: { tenant: Tenant }) {
  const [rows, setRows] = useState<{ id: string; name: string }[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [r, setR] = useState<ActivityRecord | null>(null);
  useEffect(() => {
    api<{ id: string; name: string }[]>(`/api/tenants/${tenant.id}/inventory/activities`).then((a) => {
      setRows(a);
      if (a.length === 1) setOpen(a[0].id);
    });
  }, [tenant.id]);
  useEffect(() => {
    if (open) api<ActivityRecord>(`/api/tenants/${tenant.id}/inventory/activities/${open}`).then(setR);
  }, [tenant.id, open]);
  return (
    <section>
      <h1>Inventory</h1>
      <p className="muted">What {tenant.name} records about each processing activity: its systems, AI models, data,
        the people affected and who receives their information. System owners keep it current.</p>
      {rows.length > 1 && (
        <ul className="plain">{rows.map((x) => <li key={x.id}><button className="link" onClick={() => setOpen(x.id)}>{x.name}</button></li>)}</ul>
      )}
      {r && <div className="card"><h2>{r.name}</h2><InventoryRecord r={r} /></div>}
    </section>
  );
}
