export type Me = {
  id: string;
  username: string;
  display_name: string;
  tenants: { id: string; name: string; roles: string[] }[];
  workspace_roles: { workspace_id: string; role: string }[];
};

export type Tenant = {
  id: string;
  name: string;
  approval_preset: string;
  intended_use_acknowledged: boolean;
  intended_use_ack_at: string | null;
  my_roles: string[];
  my_workspace_roles: string[];
  allowed_actions: string[];
};

export type AuditEvent = {
  seq: number;
  occurred_at: string;
  actor_type: string;
  actor_name: string;
  actor_roles: string[];
  on_behalf_of: string | null;
  action: string;
  object_type: string | null;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
};

export type Verification = {
  ok: boolean;
  events_checked: number;
  first_broken_seq: number | null;
  problem: string | null;
};

export const ROLE_LABELS: Record<string, string> = {
  submitter: "Submitter",
  system_owner: "System owner",
  privacy_analyst: "Privacy analyst",
  privacy_counsel: "Privacy counsel",
  dpo: "DPO",
  tenant_admin: "Tenant admin",
  workspace_admin: "Workspace admin",
  auditor: "Auditor",
};
