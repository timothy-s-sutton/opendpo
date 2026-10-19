# Threat model

**Status:** first version, written against the design before the code exists. It will be revised as each component is built, and again for the project's own self-assessment.

**Scope:** a self-hosted OpenDPO install serving one organization or a consultancy with several client tenants. The hosted read-only sandbox planned after v1 will get its own threat model.

**Method:** STRIDE per trust boundary, with AI-specific threats mapped to the OWASP Top 10 for LLM Applications and the OWASP Top 10 for Agentic Applications. Items are cited by identifier only.

## Assets

| Asset | Why it matters |
| --- | --- |
| Assessment records and approvals | They are the organization's evidence of compliance; a forged approval is a false record |
| Audit log | Proves who did what; loses all value if it can be edited silently |
| Tenant data (inventory, intake answers, uploads) | May describe personal data processing, vendors and internal systems; cross-tenant exposure breaches client confidentiality |
| Policy positions and content packs | Drive what the rules engine decides; tampering changes legal conclusions |
| Credentials and API keys | Keycloak admin, database, Anthropic API key |

## Actors

Legitimate users in eight roles; an insider with a valid role trying to exceed it; another tenant's user; an attacker with network access to the install; a malicious document author whose upload reaches the agent; and the AI model itself, treated as untrusted output.

## Threats and mitigations

| ID | Threat | STRIDE | Mitigation | Requirement |
| --- | --- | --- | --- | --- |
| T-01 | A user reads or changes another tenant's records through a missing filter in application code | Information disclosure, tampering | PostgreSQL row-level security on every tenant table, so the database refuses cross-tenant rows even if code forgets; tests that try cross-tenant reads | PLT-01 |
| T-02 | An analyst approves their own high-risk assessment | Elevation of privilege | Rego SOD-1 and SOD-2 checks at the approval endpoint, using the assessment's audit history | PLT-06 |
| T-03 | Prompt injection in an uploaded document makes the agent change a triage result or skip a finding | Tampering | Triage is decided by Rego rules, not the model; uploaded text is delimited as data; agent output is schema-validated; an analyst confirms triage | ARC-03, WF-05, WF-06; OWASP LLM01 |
| T-04 | The agent cites a clause that does not exist, or invents a legal requirement | Spoofing (of authority) | Every citation must resolve to a stored, verified clause or policy position, or the draft fails validation before anyone sees it | ARC-02; OWASP LLM09 |
| T-05 | The agent is induced to call an approval or mapping endpoint | Elevation of privilege | The agent identity holds no role; those endpoints refuse it regardless of what the model requests | ARC-01, SOD-6; OWASP LLM06, Agentic excessive agency |
| T-06 | An insider edits or deletes an audit event to hide an action | Tampering, repudiation | Append-only table, no update or delete grant for any role, SHA-256 hash chain verified daily and before export, alerts on a break | PLT-41, PLT-43, SOD-5 |
| T-07 | A tampered or unverified content pack changes legal conclusions | Tampering | Loader refuses rules without a CNT-01 verification record; in v1, content bundles are signed and the signature is checked before import | CNT-01, UPD-04 |
| T-08 | Personal data in intake answers or uploads is sent to the model provider beyond what is needed | Information disclosure | Send only the fields a task needs; document data flows to the provider in the project's own DPIA; demo data is fictional | USE-06 |
| T-09 | Default credentials or exposed admin consoles on a self-hosted install | Spoofing, elevation of privilege | No default production passwords; demo credentials clearly marked and generated per install; Keycloak admin and database ports bound to localhost by default | Secure defaults |
| T-10 | An admin grants themselves a higher role | Elevation of privilege | SOD-4: another admin must change an admin's roles; role changes are audit events | PLT-06 |
| T-11 | Model or provider outage blocks work | Denial of service | Rules engine and review queue work without the model; drafting retries or waits; provider sits behind an interface so another can be swapped in | Model access |
| T-12 | A user denies having approved an assessment | Repudiation | Approval records name, role and timestamp, written to the hash-chained log | PLT-32 |

## Out of scope for this version

Hardening for public internet exposure, high availability, and backups. OpenDPO is a proof of concept intended to run locally or on a private network.
