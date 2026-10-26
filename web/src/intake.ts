// Types and helpers for the intake form and triage results (WF-01 to WF-08).

export type Condition = {
  fact?: string;
  equals?: unknown;
  in?: unknown[];
  contains?: unknown;
  at_least?: number;
  all?: Condition[];
  any?: Condition[];
  not?: Condition;
};

export type Definition = {
  id: string;
  citation: string;
  summary: string;
  text: string;
  source: string;
  source_url: string;
  location: string | null;
  verified: boolean;
};

export type Choice = { const: string; title: string };

export type Property = {
  title: string;
  description?: string;
  type?: string;
  oneOf?: Choice[];
  items?: { oneOf: Choice[] };
  "x-opendpo": {
    section: string;
    type: "text" | "textarea" | "date" | "boolean" | "choice" | "multichoice" | "number";
    show_when: Condition[];
    pack?: string;
    definitions?: Definition[];
    rules_usable?: boolean;
    placeholder?: string;
    sensitive_options?: string[];
  };
};

export type SectionInfo = {
  id: string;
  title: string;
  rules_usable?: number;
  rules_total?: number;
};

export type IntakeForm = {
  schema: {
    properties: Record<string, Property>;
    "x-opendpo-sections": SectionInfo[];
  };
  scoping: Record<string, unknown>;
  ai_question: string;
  content_versions: Record<string, string>;
};

export type Answers = Record<string, unknown>;

export type Citation = {
  id: string;
  citation: string;
  summary: string;
  location: string | null;
  source: string;
  source_url: string;
};

export type Explained = {
  rule: string;
  pack: string;
  pack_version: string;
  kind: string;
  title: string;
  result: Record<string, unknown>;
  explanation: string;
  facts_tested: string[];
  citations: Citation[];
};

export type TriageResult = {
  classifications: Explained[];
  assessments: { assessment: string; pack: string; triggered_by: Explained[] }[];
  obligations: Explained[];
  not_run: { rule: string; pack: string; title: string; problems: string[] }[];
  content_versions: Record<string, string>;
  rounds: number;
};

export type Change = { action: "add" | "remove"; rule?: string; item?: string; reason: string };

export type ProjectDetail = {
  id: string;
  name: string;
  status: "draft" | "awaiting_clarification" | "triaged" | "confirmed";
  answers: Answers;
  clarification: string | null;
  created_by_name: string | null;
  updated_at: string;
  submissions: { version: number; submitted_at: string; submitted_by_name: string }[];
  triage: null | {
    id: string;
    status: "proposed" | "confirmed" | "superseded";
    result: TriageResult;
    created_at: string;
    submission_version: number;
    decision: null | { decision: "confirm" | "change"; changes: Change[]; note: string | null };
    decided_at: string | null;
    decided_by_name: string | null;
  };
};

export type ProjectRow = {
  id: string;
  name: string;
  status: ProjectDetail["status"];
  updated_at: string;
  created_by_name: string;
  version: number | null;
};

const MISSING = Symbol("missing");

// Same semantics as policy/triage.rego and api/opendpo/conditions.py. Used only to
// decide which questions show; triage itself always runs in the policy engine.
export function holds(c: Condition, facts: Answers): boolean {
  if (c.fact !== undefined) {
    const v = c.fact in facts ? facts[c.fact] : MISSING;
    if (v === MISSING || v === undefined) return false;
    if ("equals" in c) return v === c.equals;
    if ("in" in c) return (c.in ?? []).some((x) => x === v);
    if ("contains" in c) return Array.isArray(v) && v.includes(c.contains);
    if ("at_least" in c) return typeof v === "number" && v >= (c.at_least ?? 0);
    return false;
  }
  if (c.all) return c.all.every((x) => holds(x, facts));
  if (c.any) return c.any.some((x) => holds(x, facts));
  if (c.not) return !holds(c.not, facts);
  return false;
}

// Questions showing for these answers, in form order. A question shown only because of
// a hidden question's answer is hidden too, matching the API's pruning.
export function visibleIds(form: IntakeForm, answers: Answers): string[] {
  const kept: Answers = {};
  const shown: string[] = [];
  for (const [id, p] of Object.entries(form.schema.properties)) {
    if (p["x-opendpo"].show_when.every((c) => holds(c, kept))) {
      shown.push(id);
      if (id in answers) kept[id] = answers[id];
    }
  }
  return shown;
}

export const STATUS_LABELS: Record<ProjectDetail["status"], string> = {
  draft: "Draft",
  awaiting_clarification: "Waiting for an analyst",
  triaged: "Triaged, awaiting confirmation",
  confirmed: "Triage confirmed",
};

export const ASSESSMENT_LABELS: Record<string, string> = {
  ccpa_risk_assessment: "CCPA risk assessment",
};

export function humanize(id: string): string {
  return ASSESSMENT_LABELS[id] ?? id.replace(/_/g, " ").replace(/^\w/, (s) => s.toUpperCase());
}
