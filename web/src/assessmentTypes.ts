export type Level = "very_low" | "low" | "moderate" | "high" | "very_high";
export const LEVELS: Level[] = ["very_low", "low", "moderate", "high", "very_high"];
export const LEVEL_LABELS: Record<Level, string> = {
  very_low: "Very low", low: "Low", moderate: "Moderate", high: "High", very_high: "Very high",
};
export const ROUTING_LABELS: Record<string, string> = { low: "Low", medium: "Medium", high: "High" };
export const ASSESSMENT_STATUS: Record<string, string> = {
  draft: "Draft", in_review: "In review", returned: "Returned for changes", approved: "Approved",
  rejected: "Rejected", superseded: "Superseded",
};
export const CHECK_STATUS: Record<string, string> = {
  met: "Met", not_met: "Not met", not_yet_due: "Not yet due", not_applicable: "Does not apply", unknown: "Unknown",
};

export type LawCite = {
  id: string; citation: string; summary: string; text: string; location: string | null; source: string;
  source_url: string; verified: boolean;
};

export type Risk = {
  id: string; title: string; harm: string | null; source_and_cause: string; affected: string | null;
  framework_tags: string[]; citations: string[]; policy_refs: string[];
  likelihood: Level; severity: Level; residual_likelihood: Level | null; residual_severity: Level | null;
};
export type Safeguard = {
  id: string; title: string; description: string; status: "planned" | "in_place"; owner: string | null;
  addresses: string[]; citations: string[]; policy_refs: string[];
};
export type CheckItem = { ref: string; status: string; note: string; addresses: string[] };
export type Person = { name: string; position: string; provided: string | null };
export type Reviewer = {
  name: string; position: string; role: string; step: string; date: string; has_initiation_authority: boolean;
  legal_counsel: boolean; self_approval_reason: string | null;
};

export type Section = {
  id: string; number: string; title: string; kind: string; help: string; editable: boolean;
  in_regulator_report: boolean; appendix: boolean; what_the_law_says: LawCite[]; revision: number;
  body: any; last_edited_by: string | null; last_edited_by_type: "user" | "agent" | null; last_edited_at: string | null;
};

export type Harm = {
  id: string; name: string; description: string; citation: string; quote: string;
  related: { provision: string; citation: string; why: string }[]; framework_tags: string[]; usable: boolean;
  problems: string[];
};

export type Decision = {
  review_round: number; step: string; role: string; decision: string; note: string | null;
  has_initiation_authority: boolean; decided_at: string; name: string; position: string | null; user_id: string;
};

export type ReviewState = {
  status: string; round: number; routing_level: string | null;
  plan: { level: string; preset: string; provisional: string[]; final: string[]; each_final_role: boolean; source: string } | null;
  next: { step: string | null; roles: string[]; done: boolean } | null;
  can_act: boolean; submitted_at: string | null; approved_at: string | null; next_review_due: string | null;
  decisions: Decision[];
};

export type Acceptance = {
  risk: string; risk_title: string; residual: Level; reason: string; review_date: string; by_name: string;
  by_position: string | null; at: string;
};

export type Assessment = {
  id: string; project_id: string; type: string; status: string; title: string; editable: boolean;
  sections: Section[]; harms: { entries: Harm[] }; framework: string;
  framework_tags: { id: string; label: string; help: string }[];
  methodology: { id: string; version: string; levels: { id: Level; label: string; likelihood: string; severity: string }[];
                 matrix: Record<Level, Level[]> };
  computed: {
    ratings: { risk: string; inherent: Level; residual: Level | null }[];
    overall_inherent: Level | null; overall_residual: Level | null;
    routing: { level: string; floor: string; from_score: string; raised_by_score: boolean };
    proceed_blockers: string[]; consistency_problems: string[]; sections_not_started: string[];
  };
  floor_rules: string[]; risk_acceptances: Acceptance[]; review: ReviewState; ai_draft_label: string | null;
  policy_versions: { policy: string; title: string; version: number }[]; notice: string;
};

export type AssessmentRow = {
  id: string; project_id: string; project_name: string; assessment_type: string; status: string;
  routing_floor: string; created_at: string; updated_at: string;
};

export type Revision = {
  revision: number; author_type: string; author_name: string; note: string | null; created_at: string;
  changes: { text?: string[]; added?: string[]; removed?: string[]; changed?: Record<string, unknown> };
};
