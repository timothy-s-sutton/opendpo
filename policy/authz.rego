# OpenDPO authorization: roles, segregation of duties and the agent boundary.
# Every API action asks this policy for a decision. Auditors can read the
# rules here directly (requirements: PLT-04, PLT-05, PLT-06, SOD-1 to SOD-6).
package opendpo.authz

# Which tenant roles may perform each action (from the role table in
# docs/requirements.md). Workspace-level roles are listed separately.
role_actions := {
	"intake.submit": {"submitter", "system_owner", "privacy_analyst"},
	"intake.read": {"submitter", "system_owner", "privacy_analyst", "privacy_counsel", "dpo", "auditor"},
	"intake.clarify": {"privacy_analyst", "dpo"},
	"triage.confirm": {"privacy_analyst", "dpo"},
	"draft.edit": {"privacy_analyst", "privacy_counsel", "dpo"},
	"review.comment": {"system_owner", "privacy_analyst", "privacy_counsel", "dpo"},
	"assessment.read": {"system_owner", "privacy_analyst", "privacy_counsel", "dpo", "auditor"},
	"assessment.approve": {"privacy_analyst", "privacy_counsel", "dpo"},
	"assessment.submit": {"privacy_analyst", "privacy_counsel", "dpo"},
	"assessment.accept_risk": {"dpo"},
	"assessment.export": {"privacy_analyst", "privacy_counsel", "dpo", "auditor"},
	"inventory.read": {"system_owner", "privacy_analyst", "privacy_counsel", "dpo", "auditor"},
	"policy.read": {"submitter", "system_owner", "privacy_analyst", "privacy_counsel", "dpo", "tenant_admin", "auditor"},
	"policy.propose": {"privacy_counsel", "dpo"},
	"policy.approve": {"dpo"},
	"members.read": {"tenant_admin", "dpo", "auditor"},
	"membership.grant": {"tenant_admin"},
	"membership.revoke": {"tenant_admin"},
	"tenant.ack_intended_use": {"tenant_admin"},
	"audit.read": {"privacy_analyst", "privacy_counsel", "dpo", "tenant_admin", "auditor"},
	"audit.verify": {"privacy_analyst", "privacy_counsel", "dpo", "tenant_admin", "auditor"},
	"audit.export": {"dpo", "tenant_admin", "auditor"},
}

workspace_role_actions := {
	"membership.grant": {"workspace_admin"},
	"membership.revoke": {"workspace_admin"},
	"tenant.ack_intended_use": {"workspace_admin"},
	"members.read": {"workspace_admin"},
	"audit.read": {"workspace_admin"},
}

# ARC-01: the agent may read and draft, nothing else.
agent_actions := {"content.read", "inventory.read", "policy.read", "triage.run", "draft.write"}

default allow := false

allow if {
	count(deny) == 0
	permitted
}

permitted if {
	input.actor.type == "user"
	some role in input.actor.roles
	role in role_actions[input.action]
}

permitted if {
	input.actor.type == "user"
	some role in input.actor.workspace_roles
	role in workspace_role_actions[input.action]
}

permitted if {
	input.actor.type == "agent"
	input.action in agent_actions
}

# SOD-6: the agent never holds a role and can never approve or change
# roles, mappings or policies, whatever the model asks for.
deny contains "SOD-6: the agent identity cannot perform this action" if {
	input.actor.type == "agent"
	not input.action in agent_actions
}

# SOD-4: admins cannot change their own roles; another admin must.
deny contains "SOD-4: you cannot change your own roles" if {
	input.action in {"membership.grant", "membership.revoke"}
	input.resource.user_id == input.actor.id
}

# SOD-3: whoever proposed a policy or mapping change cannot approve it.
deny contains "SOD-3: you proposed this change, so another person must approve it" if {
	input.action == "policy.approve"
	input.resource.proposed_by == input.actor.id
}

# SOD-1: no one approves an assessment they submitted, drafted (or asked the agent to draft)
# or edited. The single-person office preset relaxes this with a recorded justification (PLT-34).
deny contains "SOD-1: you submitted, drafted or edited this assessment, so another person must approve it" if {
	input.action == "assessment.approve"
	input.actor.id in input.resource.involved
	input.tenant.approval_preset != "single_person"
}

deny contains "PLT-34: approving your own work needs a recorded justification" if {
	input.action == "assessment.approve"
	input.actor.id in input.resource.involved
	input.tenant.approval_preset == "single_person"
	not input.resource.self_approval_reason
}

# SOD-2: one person gives one approval per review round, so high risk gets two different people.
deny contains "SOD-2: you already approved this assessment in this round; another person must give the next approval" if {
	input.action == "assessment.approve"
	input.actor.id in input.resource.approved_this_round
}

reasons contains r if some r in deny

reasons contains "no role held in this tenant permits this action" if {
	count(deny) == 0
	not permitted
}

decision := {"allow": allow, "reasons": reasons}
