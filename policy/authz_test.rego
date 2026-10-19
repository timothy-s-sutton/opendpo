package opendpo.authz_test

import data.opendpo.authz

user(roles) := {"type": "user", "id": "u1", "roles": roles, "workspace_roles": []}

test_auditor_reads_audit if {
	authz.allow with input as {"actor": user(["auditor"]), "action": "audit.read"}
}

test_submitter_cannot_read_audit if {
	not authz.allow with input as {"actor": user(["submitter"]), "action": "audit.read"}
}

test_auditor_cannot_approve if {
	not authz.allow with input as {"actor": user(["auditor"]), "action": "assessment.approve"}
}

test_agent_can_draft if {
	authz.allow with input as {"actor": {"type": "agent", "id": "agent", "roles": []}, "action": "draft.write"}
}

test_agent_cannot_approve_even_with_roles if {
	not authz.allow with input as {"actor": {"type": "agent", "id": "agent", "roles": ["dpo"]}, "action": "assessment.approve"}
	some r in authz.reasons with input as {"actor": {"type": "agent", "id": "agent", "roles": ["dpo"]}, "action": "assessment.approve"}
	startswith(r, "SOD-6")
}

test_admin_cannot_grant_self if {
	inp := {"actor": user(["tenant_admin"]), "action": "membership.grant", "resource": {"user_id": "u1"}}
	not authz.allow with input as inp
	some r in authz.reasons with input as inp
	startswith(r, "SOD-4")
}

test_admin_can_grant_other if {
	authz.allow with input as {"actor": user(["tenant_admin"]), "action": "membership.grant", "resource": {"user_id": "u2"}}
}

test_workspace_admin_grants if {
	authz.allow with input as {"actor": {"type": "user", "id": "w1", "roles": [], "workspace_roles": ["workspace_admin"]}, "action": "membership.grant", "resource": {"user_id": "u2"}}
}

test_proposer_cannot_approve_policy if {
	not authz.allow with input as {"actor": user(["dpo"]), "action": "policy.approve", "resource": {"proposed_by": "u1"}}
}

test_unknown_action_denied if {
	not authz.allow with input as {"actor": user(["dpo"]), "action": "made.up"}
}
