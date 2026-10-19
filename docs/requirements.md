# Privacy Office AI Platform: Requirements

Started Oct 8, 2026 by Tim Sutton. Exported from the living requirements document on Oct 19, 2026; requirement IDs are stable.

## Project identity (proposed)

This is an open-source reference implementation of a policy-driven, human-governed AI privacy office. It is not a product competing with OneTrust, Privado or Securiti. It shows how a privacy program can put AI agents to work without giving up accountability.

**Working name:** OpenDPO. An open-source data protection office: the AI drafts, the human DPO decides. The repo lives under Tim's own GitHub account. USPTO search found no live or dead marks (2026-10-08).

**Mission statement:** Show that AI can carry the analytical load of privacy operations while every decision stays traceable to the regulations that apply to the organization, its own policy, and a named human approver.

**Primary audience:** hiring managers and privacy, security and AI governance leaders reviewing Tim's work. **Secondary audience:** small privacy teams and independent consultants who want a transparent, self-hostable starting point.

**Deployment model:** self-hosted, never a hosted SaaS. One container install serves a single organization, or a consultancy serving several clients as separate tenants, so client data never leaves the operator's own infrastructure.

### What the repo demonstrates

| Lens | How the project shows it |
| --- | --- |
| Privacy professional | Assessment methodology, applicability logic, state law depth, CPPA risk assessment and ADMT alignment |
| Cybersecurity professional | Identity and role design, segregation of duties, tamper-evident audit trail, threat model, secure defaults |
| AI-enabled leader | Policy-bounded agents, human-in-the-loop by design, cited and explainable outputs, evaluation suite, and the platform governing its own AI |

**Signature move:** the project assesses itself. Its own DPIA and AI risk assessment are produced with the platform and published in the repo. That proves the tool works and shows the governance practice in one artifact.

## Goals and success criteria

The prototype succeeds when a reviewer can watch one AI system go from intake to an approved, auditable AI and ADMT risk assessment in under 10 minutes.

1. **Runs anywhere in one step.** A single container setup starts the platform with a seeded consultant workspace holding three fictional client tenants, each with its policies and sample users in every role.
2. **One complete workflow, end to end.** Scoping, intake and triage, agent-drafted AI and ADMT risk assessment, reviewer edits, approval and audit record all work. Three demo scenarios, below, exercise different rules and triage outcomes.
3. **Every agent output is explainable.** Each finding cites the policy clause and the regulatory or framework provision it relies on, and records the policy and content versions used.
4. **No decision without a human.** The agent cannot approve, finalize or change a mapping. Approval requires a named user in an authorized role.
5. **Agent quality is measured.** An evaluation suite of test scenarios checks triage and assessment drafts against expected outcomes, with results in the repo.
6. **Keeps pace with unsettled rules.** AI regulation is still changing. The demo shows a regulatory content update flowing through human-reviewed mapping changes into a reassessment, using Colorado's real history: a seeded assessment made under the original Colorado AI Act (SB 24-205) receives the SB 26-189 update.
7. **The repo reads like a program, not just code.** README, architecture overview, threat model, AI governance statement and the self-assessment are all included.

**Guiding principle:** for every build choice, favor the stronger story over the faster path, since OpenDPO is a portfolio showpiece.

**Companion deliverables:** project documentation, a walkthrough deck and a script for a recorded demo, each planned so the build produces the moments they show.

### Demo scenarios

Each scenario is chosen to make triage reach a different conclusion, so the demo shows judgment rather than one fixed path.

The demo seeds one consultant workspace with three fictional client tenants, one per scenario, so it shows multi-tenancy and three triage outcomes at once.

| Demo tenant | Scenario | Decision type | What triage should conclude | Key rules exercised |
| --- | --- | --- | --- | --- |
| Harbor Staffing | AI resume screening | Employment: ranks and filters applicants | ADMT for a significant decision; high risk | CPPA ADMT and risk assessment rules; NYC Local Law 144 bias audit if hiring in NYC; Colorado SB 26-189 if hiring in Colorado; California FEHA automated-decision rules; Illinois HB 3773, plus the AI Video Interview Act if it analyzes video interviews; EU AI Act high risk (employment) and the workplace emotion-recognition ban only with an EU footprint |
| Ridgeline Card Services (for-profit consumer card issuer) | AI credit decisioning agent | Financial: approves, declines or prices credit | ADMT and high risk; CCPA applies to the issuer, but GLBA-covered card-account data and FCRA-covered activity are exempt at the data level, so triage separates card data from marketing and website data | ECOA and Reg B adverse action notices, FCRA, GLBA, Colorado SB 26-189, whose disclosures compliant ECOA or FCRA notices can also satisfy, EU AI Act high risk (creditworthiness) with an EU footprint |
| Lumen Outfitters | AI marketing personalization engine | Marketing: infers interests, builds lookalike audiences, generates personalized offers and ad copy | Not ADMT for a significant decision, since advertising is excluded, but a risk assessment is still required for sharing data for cross-context behavioral advertising and for sensitive inferences | CPPA risk assessment triggers, CCPA opt-out of sale and sharing, Colorado Privacy Act assessment and opt-outs with enough Colorado consumers, GDPR profiling, DPIA and right to object, ePrivacy consent |

## Scope

Version 1 builds one thin vertical slice: scoping through an approved AI and ADMT risk assessment. Everything else is designed for in the data model but not built.

**Scope watch:** the scope below was accepted as it stands on 2026-10-18. From here on, any addition beyond this document is flagged as potential scope creep before it is adopted.

### Version 1: build

| Capability | Boundary for v1 |
| --- | --- |
| Tenancy | Three levels: workspace, tenant and membership. A consultant workspace holds several client tenants; a single organization runs one tenant and never sees the tenant switcher |
| Users and roles | Local accounts in Keycloak; eight default roles held on tenant memberships; approval presets per tenant (standard, lean, single-person office); segregation of duties written as Rego policies in Open Policy Agent |
| Scoping | Plain-language guided questionnaire in six parts that sets the tenant's applicability profile; evaluates US and EU law on a jurisdiction-agnostic design; collects every US state |
| Policy library | Open policy templates as a stand-in for an org's real policies: a typical, standardized set covering the policies NIST CSF 2.0 and the NIST Privacy Framework require, such as an acceptable use policy and incident response plan. They power the demo; import of an org's own policies replaces them, with agent-extracted rules confirmed by a human. Seventeen OpenDPO-authored templates, seven fully written and ten as outlines; each tenant edits its own copy |
| Crosswalk and applicability | Full mappings: GDPR, CCPA/CPRA with CPPA ADMT and risk assessment rules, Colorado SB 26-189, plus the original Colorado AI Act (SB 24-205) as a historical pack for the update demo, EU AI Act, NIST AI RMF, OWASP Top 10 for LLM Applications, privacy principles (FIPPs and OECD). Applicability and citation only: ECOA and Reg B, FCRA, GLBA, NYC Local Law 144, ePrivacy, plus Colorado Privacy Act, California FEHA automated-decision rules, Illinois HB 3773 and AI Video Interview Act, and federal anti-discrimination law (Title VII, ADA, ADEA), added in planning (see C3). AI risk sources cited by ID: NIST AI 600-1, MITRE ATLAS, OWASP Top 10 for Agentic Applications. ISO/IEC 42001 parked pending license research; no CRI Profile text. Everything passes the content verification gate; effective dates verified at build time |
| Intake and triage | Dynamic intake form: nine core questions and six branches. Deterministic rules decide which assessments apply; the agent explains why with citations; an analyst confirms |
| AI and ADMT risk assessment | Shared risk-assessment engine on the nine content elements of CPPA section 7152, a 5-by-5 NIST SP 800-30 scale and a unified harm taxonomy; agent draft, reviewer edit, approval; one assessment yields a full internal assessment and a regulator-ready report. The DPIA uses the same form with GDPR sections added |
| Regulatory content updates | Versioned content packs per law, delivered as signed bundles; each tenant's DPO adopts an update after a side-by-side dry run; affected assessments flagged with risk-tiered due dates; in-app and email notifications |
| Inventory | Seven entities centered on the processing activity: processing activities, systems, AI components, data categories, data subject groups, vendors and transfers (transfers optional); vendor information requests and model cards, with a fast track |
| Review queue | Routing by risk level under the tenant's approval preset; approve, reject or return; internal review notes and clarification requests on every submission |
| Audit trail | Append-only, hash-chained event log with JSON export; chain verified daily and before every export, with alerts on a break |
| Agent evaluation | Scenario fixtures for the three tenants plus edge cases; triage scored by exact match; drafts scored on citation validity, section coverage and a quality rubric; runs in continuous integration with results in the repo |
| Packaging and demo | Docker Compose with seeded demo data; run-it-yourself plus a recorded demo |

### Designed for, built later

- PIA, TIA and LIA templates
- SSO, federation and SCIM provisioning
- SIEM forwarding of audit events
- Automated regulatory monitoring and news feed
- DSAR handling, breach notification analysis, vendor and DPA review
- Data map, system map and flow diagram generation; owner re-certification
- Hosted read-only sandbox that replays cached agent outputs with no live model calls, resets nightly and has its own threat model
- Comprehensive privacy laws for the remaining US states, and further countries such as Canada, Brazil, Saudi Arabia and China, as content packs
- Full text for the ten outline policies
- Further AI security sources: CISA and UK NCSC Guidelines for Secure AI System Development, NIST AI 100-2, NIST SP 800-218A, Google SAIF and the CSA AI Controls Matrix, each after a license check
- Switch policy templates to Privacy Framework 1.1 once NIST publishes the final
- Licensed content import (potential scope creep, flagged 2026-10-18): a licensee imports its own copy of a restricted standard such as ISO/IEC 42001 or the CRI Profile, records its license details, and sees full text beside OpenDPO's clause IDs in its own instance only
- EU AI Act Article 50 transparency checks (AI interaction disclosure, deepfake and public-interest text labelling), added when a scenario needs them
- Automatic, opt-in scheduled pull of signed content bundles
- Expansion into a general GRC platform

### Out of scope

- Hosted SaaS offering or commercial support
- Real client data in the public repo
- Legal advice: outputs are drafts for qualified review
- Automatic approvals or automatic changes to mappings
- Building identity infrastructure from scratch

## Design principles

1. **Policy decides, the agent applies.** Agents reason only from the tenant's confirmed policy positions and the curated regulatory content, never from open-ended judgment.
2. **Humans own every decision.** Agents draft and recommend. Approvals, mapping changes and policy changes require a named person.
3. **Everything is traceable.** Each output links to its inputs, citations, policy version and approver.
4. **Org or consultant.** Usable by a single organization on its own or by a consultant managing several clients.
5. **Minimal burden on submitters.** Forms ask the least needed and branch only when an answer requires it.
6. **Transparent and editable content.** Crosswalks and mappings are visible, reviewable and overridable by legal and compliance teams.
7. **Extensible by design.** The data model uses generic objects (obligations, controls, assessments, evidence, owners) so privacy is the first module, not the only one.
8. **Use standards, don't reinvent them.** Standard protocols for identity, structured events for audit, and public frameworks for content.
9. **Rules decide, the agent explains.** Applicability and triage come from deterministic rules, so the same answers always give the same result; the model never decides whether a law applies.
10. **Verified content only.** Nothing enters a mapping, the rules engine or the harm taxonomy until it is checked against primary text.

## Intended use and disclaimers

OpenDPO is a proof of concept built by a privacy practitioner, not by lawyers. It does not give legal advice and does not replace qualified human review and decisions; this must be stated everywhere a user meets its output.

- **USE-01** The README, documentation site and license file open with a notice: OpenDPO is a proof of concept, provides no legal advice, and is not a substitute for review and decisions by qualified privacy, legal and compliance professionals.
- **USE-02** Every agent draft in the app carries a visible label: AI-generated draft, not legal advice, requires qualified human review.
- **USE-03** Every exported assessment carries the same notice, alongside the named reviewers and approver.
- **USE-04** Onboarding requires an admin to acknowledge the intended-use notice before first use; the acknowledgment is logged in the audit trail.
- **USE-05** Regulatory content shows its as-of date and source, with a note that rules change and must be verified.
- **USE-06** Demo data is fictional; the docs say so and warn against loading real personal data into a public demo instance.

* **USE-07** The documentation states openly that OpenDPO has one maintainer, who both authors and verifies regulatory content, and that each rule records this; a second reviewer is added once the project has contributors.

## Platform requirements

Five shared components serve every workflow. Requirement IDs are stable so later documents can reference them.

See the platform flow diagram in [architecture.md](architecture.md).

Agents read from the policy library and crosswalk; the review queue is the only path to an approved record, and every step writes to the audit trail.

### Tenancy, users and roles

- **PLT-01** Each tenant's data, policies and users are isolated from other tenants.
- **PLT-02** Three levels: workspace (a consultant firm, or one organization using OpenDPO for itself), tenant (one client organization with its own policies, scope, inventory, assessments and audit log) and membership (a user's role in one tenant). A consultant workspace can create and switch between client tenants; a single organization runs one tenant and never sees the switcher.
- **PLT-03** Admins create local accounts in Keycloak (username, email, password) and assign roles through tenant memberships.
- **PLT-04** Roles are configurable and live on memberships, not users, so one consultant can be an analyst for one client and the outsourced DPO for another. Eight defaults, with permissions as in the role table below: submitter, system owner, privacy analyst, privacy counsel, DPO, tenant admin, workspace admin and auditor.
- **PLT-05** Permissions are set per role and per assessment type.
- **PLT-06** Segregation of duties rules SOD-1 to SOD-6 apply, below; SOD-1 and SOD-2 relax only under the lean or single-person office preset.
- **PLT-07** (Later) SSO through SAML and OIDC, federation with Entra ID or Okta, SCIM provisioning from SailPoint or AD, configured in the Keycloak instance v1 already ships.

* **PLT-08** Anyone holding a role is treated the same, whether employee, consultant, temp or contractor: same permissions, same visibility upstream, same audit trail. Any role, including DPO, can be held by an outside party through a membership.
* **PLT-09** Approval rules are configurable per tenant through three presets. Standard uses the routing table below. Lean allows a single approver at every risk level. Single-person office lets one person hold the analyst and DPO roles and approve their own work, with compensating controls (PLT-34).

| Role | Submit intake | Edit drafts | Confirm triage | Review and comment | Approve assessments | Manage policies and mappings | Manage users | Read audit log |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Submitter (business requester) | Yes | Own only |  | Own only |  |  |  |  |
| System owner | Yes | Own systems |  | Yes |  |  |  |  |
| Privacy analyst | Yes | Yes | Yes | Yes | Low risk; provisional for medium and high |  |  | Yes |
| Privacy counsel |  | Yes |  | Yes | Medium risk | Propose |  | Yes |
| DPO |  | Yes | Yes | Yes | All levels | Approve |  | Yes |
| Tenant admin |  |  |  |  |  | Configure | Tenant | Yes |
| Workspace admin |  |  |  |  |  |  | Workspace | Yes |
| Auditor |  |  |  | Read only |  |  |  | Yes |

**Approval routing, standard preset.** The analyst does the heavy lifting at every level; counsel and the DPO review a worked draft and can approve, reject or return it to the analyst. The risk level used for routing is set in two steps. At triage, the category sets a floor: ADMT for a significant decision, or high-risk AI, is high. Once the draft is scored, an inherent rating above that floor raises the level, and a lower rating never reduces it. Routing uses inherent risk; residual risk drives the DPO's risk acceptance instead. This rule is a default approval-rule policy position that tenants can change.

| Risk level | Privacy analyst | Final approval |
| --- | --- | --- |
| Low | First-line review and final approval, by an analyst who did not draft or submit it | Analyst |
| Medium | First-line review, feedback to the submitter and a provisional approval | Privacy counsel |
| High (ADMT for a significant decision, or high-risk AI) | First-line review, feedback to the submitter and a provisional approval | DPO and privacy counsel, two different people |

**Segregation of duties**

- **SOD-1** No one approves an assessment they submitted, drafted or substantively edited. Relaxed only under the single-person office preset, with compensating controls.
- **SOD-2** High-risk assessments need two distinct approvers under the standard preset; lean and single-person presets allow one.
- **SOD-3** The person who proposes a policy or mapping change cannot approve it.
- **SOD-4** Admins cannot change their own roles; another admin must.
- **SOD-5** No role can edit or delete audit events.
- **SOD-6** The agent acts under a system identity, logged with the user who triggered it. It cannot hold a role, so it can never approve.

### Policy library

- **PLT-10** Open policy templates stand in for an org's real policies: seventeen policies covering what NIST CSF 2.0, the NIST Privacy Framework and the NIST AI RMF expect, seven fully written for v1 and ten as outlines (table below). Neither CSF 2.0 nor the Privacy Framework names policies, so the mapping is presented as OpenDPO's interpretation. They power the demo; real use replaces them through import.
- **PLT-11** Orgs can import their own policy documents.
- **PLT-12** The agent extracts candidate policy positions (risk appetite, approval thresholds, approved transfer mechanisms, retention defaults) for human confirmation. Each position is a structured record, as in the example below, of one of six types: requirement, prohibition, threshold, approval rule, default, or conditional permission (allowed only if, such as vendor AI training on company data only with a signed DPA and DPO approval).
- **PLT-13** Policies and positions are versioned; every assessment records the version it used.
- **PLT-14** Frameworks (what controls should exist) are stored separately from policy positions (the org's actual rules).

* **PLT-15** Templates are written by OpenDPO, informed by research into several open templates first. Reused text must come from a source licensed compatibly with CC BY 4.0 (public domain, CC0, CC BY or similar); share-alike, non-commercial and no-derivatives sources are excluded. Each template records its source, license and attribution.
* **PLT-16** NIST publications supply structure and terminology. Best-practice guidance, such as CSF 2.0 implementation examples and informative references and Privacy Framework guidance and crosswalks, aligns each policy's content.
* **PLT-17** No CRI Profile text in the repo, since it is licensed CC BY-NC-ND 4.0. Templates reference CRI diagnostic statement IDs with OpenDPO's own summaries, and users who hold their own rights can import CRI locally.
* **PLT-18** Templates peg to Privacy Framework 1.0 codes and store each policy's 1.1 draft equivalent from NIST's published 1.0-to-1.1 Core mapping. When 1.1 is final, the switch ships as a regulatory content update.
* **PLT-19** Each tenant gets its own copy of the templates, recording the template version it came from. When a template improves, the tenant is notified with a diff it can adopt or ignore; nothing merges automatically.

| Policy | v1 depth | Main anchors |
| --- | --- | --- |
| AI governance and acceptable AI use | Full | AI RMF Govern; CSF GV.PO |
| Privacy and AI risk assessment (PIA, DPIA, ADMT) | Full | PF ID.RA-P; AI RMF Map and Measure |
| Privacy program policy | Full | PF GV.PO-P, CT.PO-P |
| Data retention and disposal | Full | PF CT.DM-P; CSF PR.DS |
| Third-party and supplier risk management | Full | CSF GV.SC; PF ID.DE-P |
| Incident response plan, including breach notification | Full | CSF RS.MA, RS.CO, RC.RP |
| External privacy notice | Full | PF CM.AW-P |
| Information security policy | Outline | CSF GV.PO, GV.RR |
| Risk management policy | Outline | CSF GV.RM, ID.RA |
| Acceptable use policy | Outline | CSF PR.AA, PR.AT |
| Access control and identity | Outline | CSF PR.AA |
| Asset management and data classification | Outline | CSF ID.AM, PR.DS; PF ID.IM-P |
| Secure configuration, change and vulnerability management | Outline | CSF PR.PS, ID.RA |
| Logging and monitoring | Outline | CSF DE.CM, DE.AE |
| Business continuity and disaster recovery | Outline | CSF RC.RP |
| Security and privacy awareness training | Outline | CSF PR.AT; PF GV.AT-P |
| Individual rights requests procedure | Outline | PF CT.DM-P |

Privacy Framework codes are version 1.0.

```yaml
id: POS-AI-007
policy: AI Governance and Acceptable AI Use, section 4.2
statement: >
  An AI system that materially influences an employment or credit
  decision requires human review before an adverse outcome is communicated.
type: requirement   # requirement | prohibition | threshold | approval_rule | default | conditional_permission
applies_to:
  decision_domains: [employment, lending]
parameters:
  human_review: before_adverse_outcome
framework_refs: [AI RMF GOVERN, CSF GV.PO]
status: confirmed   # proposed (agent-extracted) | confirmed | retired
confirmed_by: dpo@harbor.example
version: 1.2
effective: 2026-11-01
```

### Scoping and crosswalk

- **PLT-20** Scoping is a plain-language guided questionnaire in six parts (table below). Answers are mostly closed: yes, no or not sure; picklists; bands. The rules engine maps answers to legal status and shows its reasoning.
- **PLT-21** Scoping produces an applicability profile marking every law as applies, partially applies, exempt or not applicable, each with a reason, citation and as-of date.
- **PLT-22** The crosswalk maps obligations across regulations and frameworks, with a citation for every mapping.
- **PLT-23** Base mappings are maintained centrally; tenants layer their own overrides on top.
- **PLT-24** When a base mapping changes under a tenant override, the conflict is flagged for review.
- **PLT-25** Mapping changes proposed by an agent require human approval.

* **PLT-26** "Not sure" routes a scoping question to an analyst. Consultants and analysts get an expert view to set statuses directly, and the agent can pre-fill answers from uploaded documents such as a privacy notice.
* **PLT-27** v1 evaluates US and EU law on a jurisdiction-agnostic design: footprint is captured as ISO 3166 country and subdivision codes, footprint questions are generic patterns (establishment, offering goods or services to residents, monitoring them), and each law is a content pack whose rules reference those codes and patterns. New countries are added as content, not code.
* **PLT-28** Consumer volumes per state are captured in bands whose edges sit on legal thresholds (for example 25,000 and 100,000), so no band straddles one. Scoping collects every US state now; comprehensive state privacy laws join over time as content packs, tracked as a roster rather than a fixed number.
* **PLT-29** Tenant consumer counts drive law applicability, are refreshed on a schedule and are never edited from a project. A project count above the tenant figure, or a project entering a new state, flags the tenant scope for re-check.

| Scoping part | Questions |
| --- | --- |
| A. Organization | Legal name; for-profit or nonprofit; industry; employee count; annual global gross revenue |
| B. Regulated status | GLBA financial institution; creditor under ECOA; consumer reporting agency or user of consumer reports; HIPAA covered entity or business associate; employer or employment agency hiring in NYC |
| C. Footprint | Countries and subdivisions where it does business; establishment; offers goods or services to, or monitors, people in each jurisdiction |
| D. Data volume | Consumers or households per state, in bands; share of revenue from selling or sharing personal information |
| E. Data types | Sensitive categories (health, biometric, precise geolocation, children's, financial account, government ID); applicant and employee data |
| F. AI use | Uses AI or ADMT; decision domains (employment, lending, housing, insurance, education, health care); role as developer, provider or deployer |

### Regulatory content

- **CNT-01** Content verification gate: nothing enters a mapping, the rules engine or the harm taxonomy until it has been checked against primary text (statute, regulation or official publication). Each rule records its primary citation, the date verified and who verified it. Law firm and vendor summaries are for discovery only, never the citation of record.
- **CNT-02** Regulatory content and policy positions are versioned packs written in YAML; every agent output records the versions it used.
- **CNT-03** Every outside source passes a license check before use. Sources whose terms bar redistribution or adaptation (ISO/IEC 42001, the CRI Profile, and OWASP material if share-alike) are cited by ID with OpenDPO's own summaries, never copied.
- **CNT-04** The applicability research below, checked against current sources on 2026-10-08 and re-checked in session 2, is research, not verified content, until it passes CNT-01.

| Law | Applies when | Key dates and duties |
| --- | --- | --- |
| CCPA/CPRA and CPPA regulations | For-profit doing business in California and one of: global gross revenue over $26,625,000 (2025 adjusted); buys, sells or shares personal information of 100,000+ California consumers or households; or 50%+ of revenue from selling or sharing it. Data-level exemptions for GLBA-covered data, FCRA-covered activity and HIPAA protected health information | Risk assessments from Jan 1, 2026; ADMT duties by Jan 1, 2027; pre-2026 processing assessed by Dec 31, 2027; first submission Apr 1, 2028 |
| Colorado SB 26-189 | Doing business in Colorado and developing or deploying ADMT that processes personal data and materially influences a consequential decision in education, employment, housing, financial or lending services, insurance, health care or essential government services. Advertising excluded; sectoral overlays for HIPAA entities, insurers and creditors | Decisions on or after Jan 1, 2027; AG rules due the same date; 60-day cure period until Jan 1, 2030 |
| Colorado Privacy Act | Controller doing business in or targeting Colorado with 100,000+ consumers a year, or 25,000+ plus revenue or discounts from selling personal data. Employment data excluded | In force since Jul 1, 2023; data protection assessments for targeted advertising, sale, sensitive data and certain profiling; opt-outs |
| EU AI Act | Provider or deployer placing an AI system on the EU market or using its output in the EU. Annex III high risk covers employment and creditworthiness | Prohibited practices since Feb 2, 2025, including workplace emotion recognition; Annex III high-risk duties from Dec 2, 2027 under Regulation (EU) 2026/1744 |
| GDPR | EU establishment, or offering goods or services to or monitoring people in the EU | In force; Article 22 automated decisions, Article 35 DPIA |
| NYC Local Law 144 | Employer or employment agency using an automated employment decision tool for NYC candidates or employees | In force; annual independent bias audit, public summary, 10 business days' notice |
| California FEHA automated-decision rules | Employer in California using an automated-decision system for employment decisions | In force since Oct 1, 2025; anti-discrimination; four-year data retention; limits on disability-related inquiries |
| Illinois HB 3773 and AI Video Interview Act | Employer using AI in employment decisions about Illinois workers or applicants; AI analysis of video interviews | HB 3773 in force since Jan 1, 2026 (rules proposed May 2026, withdrawn June 2026); video act: notice, explanation and consent |
| Federal anti-discrimination (Title VII, ADA, ADEA) | Covered employers, whether a tool or a person decides | In force; disparate impact applies to AI-driven selection |
| ECOA and Reg B | Creditor taking adverse action | In force; adverse action notice with specific principal reasons regardless of model complexity |
| FCRA | Uses consumer reports in decisions | In force; adverse action notice duties |
| GLBA | Financial institution | In force; privacy notice and safeguards; triggers the CCPA data-level exemption |
| ePrivacy | Stores or reads information on EU users' devices | In force; prior consent for non-essential tracking |

### Review queue

- **PLT-30** Work items route to roles based on assessment type and risk level, under the tenant's approval preset and the routing table above.
- **PLT-31** Reviewers can approve, reject or return with comments.
- **PLT-32** Nothing is final without required sign-off; the approver's name, role and date are recorded.

* **PLT-33** Every submission has two channels. Internal review notes are visible to everyone in the review and approval tree but not to the submitter or system owner. Clarification requests go back to the submitter and are logged with the reply. There is no consultant-only channel.
* **PLT-34** Under the single-person office preset, self-approval needs a recorded justification, a visible flag on the report and in the audit log, and an executive sign-off where the CPPA requires an approver with authority over whether the processing goes ahead.
* **PLT-35** On medium and high risk the analyst gives a provisional approval; counsel and the DPO then approve, reject or return the draft to the analyst.

### Audit trail

- **PLT-40** Every agent output, human edit, approval and configuration change is logged as a structured event.
- **PLT-41** The log is append-only and tamper-evident: each event stores a hash of the previous event, and a verification command reports the first broken link.
- **PLT-42** Events can be exported as JSON; (later) forwarded to a SIEM via syslog or webhook.

* **PLT-43** Chain verification also runs automatically every day and before every audit export. A broken chain immediately notifies the tenant admin, the DPO and every auditor, in the app and by email, naming the first broken link. The alert is itself logged and, once SIEM forwarding exists, sent there as a high-severity event.

### Technology stack and agents

The rules engine decides, the agent drafts and explains, and only the review queue, driven by people, turns a draft into an approved record.

| Layer | v1 choice | Why |
| --- | --- | --- |
| Backend | Python with FastAPI | Typed request and response models fit agent structured outputs |
| Database | PostgreSQL with row-level security and pgvector | One database enforces tenant isolation in the engine and stores content embeddings |
| Front end | React in TypeScript with JSON Schema-driven forms | Intake branches are defined once as schema and rendered automatically |
| Identity | Keycloak | Local accounts now; SSO, SAML, OIDC and SCIM later with no rework |
| Policy as code | Rego (Open Policy Agent) for roles, segregation of duties and triage rules | Auditors can read the rules directly |
| Content | YAML content packs and policy positions | Versioned, reviewable, diffable |
| Model access | Anthropic API behind a provider interface | Model-agnostic and swappable |
| Packaging | Docker Compose with seeded demo data | Meets the one-step run goal |

- **ARC-01** Agents read inventory, policy positions and regulatory content, run the triage rules, and write only to draft records. Approvals, mapping changes and policy changes are separate endpoints the agent identity cannot call.
- **ARC-02** Every agent output follows a schema, and every finding carries citation IDs that must resolve to a stored policy position or content clause. Unresolvable citations fail validation before a human sees the draft.
- **ARC-03** Text from uploaded documents is untrusted data, never instructions, with prompt-injection defenses mapped to OWASP LLM01.
- **ARC-04** The evaluation suite uses scenario fixtures for the three demo tenants plus edge cases, such as GLBA-exempt card data and advertising excluded from ADMT. Triage is scored by exact match against expected triggers; drafts are scored on citation validity, coverage of required sections and a quality rubric. Evaluations run in continuous integration with results published in the repo.

## Workflow requirements

Version 1 delivers intake and triage plus the AI and ADMT risk assessment; later workflows reuse the same intake, agent and review pattern.

### Intake and triage (v1)

- **WF-01** One project intake form serves every assessment type.
- **WF-02** The form is dynamic: nine core questions everyone answers, with six branches that appear only when an answer requires them (both below).
- **WF-03** The agent pre-fills answers from uploaded documents and asks only about gaps. Submitters confirm every low-confidence answer and every answer that drives a legal trigger. Any page with pre-filled answers opens with an instruction to review every answer before continuing; there is no attestation checkbox, and the submission is logged under the submitter's name.
- **WF-04** Answers are stored as structured data, not chat transcripts, so they are auditable and reusable.
- **WF-05** Deterministic triage rules, not the model, decide which assessments and obligations are triggered (table below). The agent turns free text and documents into structured answers, runs the rules, and explains each result in plain language with citations.
- **WF-06** A privacy analyst confirms or changes the triage result before work starts.

* **WF-07** The description field shows example prompt text that clears on focus, plus an info icon with the same guidance that stays available while typing. If the description misses what the project does and why, who uses it, whose data it touches, what decision it supports or when it goes live, the agent asks a targeted follow-up before triage.
* **WF-08** "Not sure" on the AI question sends it to an analyst, who follows up through a clarification request; the submitter updates the answer and the workflow resumes. The submitter can finish the rest of the intake meanwhile; only triage waits.
* **WF-09** A live or live-with-change stage marks the assessment as retroactive and raises its priority.

**Core questions**

1. Project name and a one-paragraph description, with guidance (WF-07)
2. Business owner and system owner
3. What decision or outcome the project supports
4. Does it use AI, a model or automated scoring? (yes, no, not sure)
5. Whose data: applicants, employees, customers, members, others
6. Which data categories: checkboxes from the inventory catalog, sensitive categories marked, an "other" option an analyst maps, and categories of linked systems pre-checked
7. Where the people are located
8. Vendors involved
9. Targeted go-live date and current stage: idea or design; build or procurement; testing or pilot; live in production; live with a planned change

| Branch | Shown when | Asks |
| --- | --- | --- |
| AI decision | AI is yes; a "not sure" goes to an analyst first (WF-08) | AI role in the decision; decision domain; human review point; model source; whether personal data trains it |
| Workforce observation | Applicants or employees, plus AI | Recording, biometrics, location tracking or other systematic observation used to infer traits |
| Marketing | Outcome is advertising, personalization or audience building | Selling or sharing data; cross-context behavioral advertising; inferences about sensitive traits; cookies and tracking |
| Credit | Decision domain is lending | Consumer reports used; adverse action process; reason codes |
| EU | People located in the EU | EU establishment; transfers out of the EEA; legal basis |
| New vendor | A vendor not in the inventory | Vendor role; contract and DPA status; vendor model training on our data |

**Triage rules**

| Assessment or obligation | Triggered when |
| --- | --- |
| CPPA risk assessment | CCPA applies and any of six significant-risk activities is present: selling or sharing; sensitive personal information; ADMT for a significant decision; profiling applicants, students, employees or contractors through systematic observation; profiling based on presence in a sensitive location; training ADMT for significant decisions or identity-verification technology |
| CPPA ADMT duties (pre-use notice, opt-out, access) | CCPA applies and ADMT substantially replaces human decision-making in a significant decision. Advertising is excluded |
| Colorado ADMT duties (SB 26-189) | Colorado consumers, and ADMT materially influences a consequential decision |
| Colorado Privacy Act data protection assessment | Colorado Privacy Act applies and processing involves targeted advertising, sale, sensitive data or certain profiling |
| Employment AI notice and anti-discrimination checks | AI makes or facilitates employment decisions about California or Illinois workers or applicants (FEHA rules, HB 3773, AI Video Interview Act) |
| GDPR DPIA | GDPR applies and processing is likely high risk, such as profiling with legal or similarly significant effects |
| EU AI Act check | EU footprint: prohibited-practice screen for every AI system, plus high-risk classification for Annex III domains such as employment or creditworthiness |
| NYC bias audit check | Automated employment decision tool used for NYC candidates or employees |
| Adverse action review | Lending decision using a model or consumer reports (ECOA, Reg B, FCRA) |
| TIA | Personal data transferred out of the EEA |
| PIA (policy default) | New processing that triggers none of the above, per the tenant's assessment policy |

Expected triage: resume screening triggers the CPPA risk assessment (plus systematic observation if it analyzes video interviews), CPPA ADMT duties, Colorado and NYC checks by footprint, and the EU AI Act check with EU candidates. Credit decisioning triggers adverse action review, Colorado ADMT duties, and CPPA items only for data outside the GLBA exemption. Marketing personalization triggers the CPPA risk assessment, no ADMT duties, and a GDPR DPIA and ePrivacy consent with EU customers.

### AI and ADMT risk assessment (v1)

- **WF-10** The rules engine classifies whether the system uses ADMT for a significant decision under CPPA rules, whether Colorado SB 26-189 covers it (ADMT that materially influences a consequential decision), and whether it is high risk under the EU AI Act; the agent explains the classification.
- **WF-11** The agent drafts the assessment against the tenant's risk methodology, in the report structure below: the nine content elements of CPPA section 7152 plus OpenDPO additions, covering purpose, data and model inputs, benefits, risks to individuals including bias and discrimination, likelihood and severity, and safeguards.
- **WF-12** Findings draw on three cited risk sources: the unified harm taxonomy (WF-25); the seven NIST AI RMF trustworthiness characteristics (valid and reliable; safe; secure and resilient; accountable and transparent; explainable and interpretable; privacy-enhanced; fair with harmful bias managed); and AI security sources, namely OWASP Top 10 for LLM Applications (only with an LLM component), OWASP Top 10 for Agentic Applications, NIST AI 600-1 and MITRE ATLAS. Privacy principles apply throughout. ISO/IEC 42001 controls join only after license research (see C2).
- **WF-13** The agent checks required obligations per the obligations checklist below: pre-use notice, opt-out, access and explanation rights, human review and bias testing.
- **WF-14** The draft draws on the inventory, and proposes an inventory update when it finds a system, model or flow not yet recorded.
- **WF-15** Reviewers edit any part of the draft; edits are logged against the agent's original.
- **WF-16** The approved assessment meets CPPA risk assessment content requirements, including named contributors and approvers, and can be exported as a document.
- **WF-17** When a content update changes an applicable obligation, affected assessments are flagged for reassessment.
- **WF-18** The DPIA shares the assessment form, with GDPR-specific sections added (such as necessity and proportionality, and Article 22 safeguards), so users learn one form; it satisfies GDPR Article 35 where it applies.

* **WF-19** Likelihood and severity each use NIST SP 800-30's five levels (very low, low, moderate, high, very high) in a 5-by-5 matrix. Severity definitions borrow NIST PRAM's framing: risk from a problematic data action, judged by its impact on individuals as well as the organization. Inherent risk maps to routing as very low or low to low, moderate to medium, and high or very high to high; the score can raise routing above the triage category but never lower it. The scale lives in the tenant's assessment policy, so an organization can substitute its own.
* **WF-20** Residual risk is re-rated after safeguards. Residual high or very high blocks a "proceed" recommendation unless the DPO records a formal risk acceptance, available at every risk level: the DPO's name, the reason, the residual risk accepted and a review date, shown in the report and the audit trail.
* **WF-21** One assessment produces two outputs: a full internal assessment, and a regulator-ready report that leaves out the benefits and negative-impact sections the CPPA does not require in the report.
* **WF-22** Scheduled re-review defaults to annual for high and very high risk, every two years for moderate and every three years for low. Tenants can adjust these, but never beyond a hard maximum taken from regulatory content as the strictest interval among applicable laws (three years under the CPPA today).
* **WF-23** A material change requires an update within 45 calendar days. Model retraining, a vendor change, an incident or a content change to an applicable obligation flags the assessment for review immediately.
* **WF-24** Each assessment version is retained while the processing continues, or five years after completion, whichever is later.
* **WF-25** Harms come from one unified taxonomy built as content: the CPPA section 7152 examples, the Colorado Privacy Act Rules' list (4 CCR 904-3, Rule 8.04(A)(6)), harms named in Virginia-model state laws and NIST PRAM's problems for individuals. Each harm is tagged with the laws that name it, so a Colorado assessment surfaces Colorado's harms, including constitutional, intellectual-privacy, unfair or deceptive treatment, intrusion and stigmatization, heightened risks to minors, and intrusion into places where people expect not to be observed. Every entry passes CNT-01, with Tim taking part in verification.

| Report section | Content | In regulator report |
| --- | --- | --- |
| 1. Purpose | Specific purpose, not generic | Yes |
| 2. Personal information | Categories, sensitive categories, minimum necessary | Yes |
| 3. Operational elements | Collection and sources, retention, consumer interaction, approximate number of consumers, disclosures, recipients; for ADMT, the logic with its assumptions and limitations, and the output and how it is used | Yes |
| 4. Benefits | To the business, consumers, other stakeholders and the public | No |
| 5. Negative impacts and risk register | Each risk with source, likelihood, severity, inherent and residual rating | No |
| 6. Safeguards | Planned safeguards mapped to each risk | Yes |
| 7. Decision | Whether the business will initiate the processing | Yes |
| 8. Contributors | People who provided information, legal counsel excepted | Yes |
| 9. Review and approval | Date, names and positions; approver must have authority over the initiation decision | Yes |
| OpenDPO additions | Applicability profile, triggers, obligations checklist, framework mapping, content and policy versions, risk acceptances, disclaimer | Appendix |

| Law | Obligations checked |
| --- | --- |
| CPPA ADMT rules | Pre-use notice; opt-out or a documented exception; access response explaining logic and output |
| Colorado SB 26-189 | Consumer disclosure; explanation after an adverse outcome; correction; human review on request; three-year records |
| NYC Local Law 144 | Independent bias audit within the past year; public summary; 10 business days' candidate notice |
| ECOA, Reg B and FCRA | Adverse action notice with specific principal reasons; consumer report disclosures |
| GDPR | Article 22 safeguards; Article 35 DPIA content |

### Later workflows

| Workflow | Core function |
| --- | --- |
| PIA | Lighter assessment for lower-risk processing, on the shared engine |
| TIA and LIA | Template-driven, high reuse of intake data |
| DSAR handling | Jurisdiction and deadline determination, verification steps, response drafting |
| Breach notification | Which states and regulators, timelines, draft notices |
| Vendor and DPA review | Compare questionnaires and contract clauses to policy positions, flag deviations |

## Data inventory

The inventory is the shared foundation for assessment data flows and the ROPA, so it is built once. Version 1 builds the seven-entity inventory the assessment needs.

### Inventory (v1)

- **INV-01** The processing activity is the center of the inventory, linked to six other entities: system, AI component, data category, data subject group, vendor and transfer, with fields as in the table below. How the AI takes part in a decision is recorded on the processing activity, not the system, because the legal tests turn on use, not technology.
- **INV-02** Sensitivity covers personal data and other sensitive information such as trade secrets and internal data.
- **INV-03** Systems can be seeded by CSV import, for example from an SSO app list or a vendor list.
- **INV-04** Processing activities link to the systems, recipients and transfer mechanisms they use. Transfers are modeled now and optional in v1, given the US focus.

* **INV-05** AI components are a separate entity from systems, since one vendor model can sit behind several systems. Systems and AI components record their origin: vendor-developed or in-house.
* **INV-06** AI role in the decision uses four values with on-screen definitions beside each choice and an example on hover. Human review is a separate field: none; review without the training or authority to change the outcome; or meaningful review by someone who can interpret the output, weighs other information and can change the decision. Together the two fields answer the CPPA and Colorado tests.
* **INV-07** Data categories are multi-selected from a plain-language catalog, each entry pre-mapped to its legal categories (CCPA categories, sensitive personal information, GDPR special categories). Submitters can add their own; an analyst maps each custom entry so the rules engine can evaluate it. Follow-up questions open only where they matter, such as volume band, source, retention and purpose.
* **INV-08** Origin decides who supplies the facts. For a vendor-developed system, OpenDPO generates a vendor information request listing exactly what the assessment needs, pre-filtered to what the inventory lacks. For an in-house system, the owner fills in a model card, ideally at design time. A system with a complete model card or vendor packet gets a fast track: the agent pre-fills most of the assessment and the analyst reviews instead of interviewing. The repo ships an example model card for the resume-screening scenario.
* **INV-09** Each processing activity records how many people it affects, by state and population type (customers, applicants, employees), with the tenant figure shown for context. Activity figures feed the assessment, such as the CPPA's approximate number of consumers; tenant figures drive applicability (PLT-29).

| Entity | Key fields | Links to |
| --- | --- | --- |
| Processing activity | Purpose (specific, not generic); legal basis; decision domain; AI role in the decision; human review; people affected by state and population type; jurisdictions; go-live date and stage | Systems, AI components, data categories, data subject groups, recipients, assessments |
| System | Name; business owner; technical owner; origin (vendor-developed or in-house); hosting; storage and processing locations; sensitivity; status | Processing activities, vendors, locations |
| AI component | Name; origin; type (traditional model or LLM); provider; version; intended use; inputs; output type; trained on personal data (yes or no); known limitations | Systems, vendors, training data categories |
| Data category | Name; sensitive flag; CCPA category; GDPR special category flag; retention period or criteria | Processing activities |
| Data subject group | Name (applicants, employees, customers, members); approximate count; jurisdictions | Processing activities |
| Vendor | Name; role (service provider, contractor, third party, processor); contract and DPA status; locations | Systems, AI components, recipients |
| Transfer (optional in v1) | From and to locations; mechanism (adequacy, SCCs, Data Privacy Framework) | Processing activities, vendors |

| AI role value | On-screen definition |
| --- | --- |
| Fully automated | The system makes the decision and it takes effect without a person reviewing it |
| Materially influences | A person decides, but the system's score, ranking or recommendation is a significant factor that can change the outcome |
| Assists | The system only summarizes, organizes, translates or presents information, and produces no score or recommendation about the person |
| None | No AI or automated scoring is involved in the decision |

**Model card fields:** intended use and out-of-scope uses; owner and version; inputs and outputs; training data sources, including any personal data; evaluation results, with fairness metrics by group; known limitations; human oversight and review points; monitoring and retraining plan.

### Later

- **INV-10** Guided walkthrough: a per-system interview with the system owner to classify data and map flows.
- **INV-11** Generated outputs: data map, system map and data flow diagrams from registry records.
- **INV-12** Periodic owner re-certification, with reminders and an admin dashboard showing overdue records.
- **INV-13** Optional connectors: data discovery tools (Purview, BigID, Varonis, Macie), CMDB (ServiceNow), IdP app catalog and AP vendor lists.

## Regulatory content updates (v1)

Law changes ship as signed content packs that the project verifies upstream and each tenant adopts on its own, after a dry run shows what changes. Detection stays manual in v1; automated monitoring is below, later.

- **UPD-01** One content pack per law or framework, with semantic versions: major for an applicability or obligation change, minor for a date or citation change, patch for editorial fixes. Each pack carries a lifecycle status (proposed, enacted, effective, superseded, repealed) and effective dates per provision. Old packs are never deleted.
- **UPD-02** A superseding pack names the pack it replaces and maps each old obligation to new ones as removed, changed, added or unchanged; that map drives the dry run and the reassessment flags.
- **UPD-03** The rules engine evaluates applicability as of a date, and the applicability profile marks laws enacted but not yet effective as "applies from" that date.
- **UPD-04** Updates are published upstream as signed bundles, imported by file or URL by a workspace admin; the signature is checked before anything is stored. Steps from detection to publication happen in the OpenDPO repo, with every change classified as editorial, date-only, applicability, obligation, new law or repeal.
- **UPD-05** Adoption is per tenant. A new tenant starts on the current content; after that, every update is shown to the tenant's users, admins and DPO and adopted through the process. Before adopting, the DPO or counsel sees a dry run: applicability and triggers under the old and new versions side by side, with a cited, plain-language agent summary. The importer cannot adopt (SOD-3).
- **UPD-06** On adoption, affected assessments are flagged and their obligations checklists rebuilt. Date-only and editorial changes trigger no reassessment. For other changes the due date is the changed provision's effective date, or, if already in effect, a window from adoption tiered by risk: high 30 days, moderate 60, low 90. Tenants can shorten these windows but not lengthen them. Until reassessed, the assessment shows "applies but not yet reassessed."
- **UPD-07** A tenant may defer adoption, including past the effective date, but the deferral, its reason and a DPO risk acceptance are recorded and shown in the app. Reminders escalate: 12 months before the effective date, then monthly until 4 months out, then 90, 60 and 30 days, then weekly once overdue. A short-notice law starts at the nearest step.
- **UPD-08** Notifications go in-app and by email for: update available, dry run ready, update adopted (daily digest), assessment flagged (immediate), reassessment due or overdue (30 and 7 days before, then on overdue), and running on superseded content (weekly from the effective date). Overdue and superseded-content alerts cannot be switched off. Every notification is an audit event.
- **UPD-09** The demo runs the Colorado history as its own segment: Harbor Staffing's January 2026 readiness assessment under SB 24-205; a date-only update for SB 25B-004 that triggers no reassessment; then SB 26-189 superseding the old pack, adopted by the DPO, with the assessment flagged and reassessed. SB 24-205 never took effect, so the demo calls it a readiness assessment, never an assessment under law in force.

## Regulatory monitoring and news feed (later)

Monitoring has two separate jobs: detecting new rules, which can be automated, and updating mappings, which always needs human approval.

- **REG-01** A news and notification feed covers privacy, AI and cybersecurity rules.
- **REG-02** Candidate sources include the IAPP, the Federal Register, state legislature trackers, EUR-Lex, the CPPA, NIST and CISA.
- **REG-03** Each item carries a status: proposed, enacted or effective, with key dates.
- **REG-04** Items are tagged by relevance to each tenant's applicability profile; non-applicable items stay visible but rank lower.
- **REG-05** For an applicable change, the agent runs an impact analysis through the crosswalk and proposes mapping updates.
- **REG-06** Proposed mapping updates enter the review queue; nothing changes until a human approves.
- **REG-07** Users get notifications for new items above a relevance threshold they set.

## Open decisions and planning queue

All eight planning sessions are resolved and folded into this document, with decisions logged below. Items still needing a decision are under Conflicts to resolve.

### Decisions needed now

- [x] Confirm the project identity and mission statement
- [x] Run a USPTO trademark search for OpenDPO: no live or dead marks found for "opendpo" (searched 2026-10-08)
- [x] Confirm the v1 boundary: resume screening is built end to end first; credit and marketing run as scenario data through the same engine and add no new features (amended 2026-10-18: their scenario-specific features are accepted into v1, see C4)
- [x] Confirm the v1 regulation and framework set, in two depth tiers (see Scope)
- [x] ISO/IEC 42001: parked until ISO's license terms are researched, before content work starts; no ISO text distributed. Resolved 2026-10-18 (C2): cite by clause ID with OpenDPO summaries, full text only by local import
- [x] Policy template set: source templates for the policies NIST CSF 2.0 and the Privacy Framework require, such as an acceptable use policy and incident response plan; CRI Profile not distributed (CC BY-NC-ND 4.0), local import only
- [x] Repo license: Apache 2.0 for code, CC BY 4.0 for templates and content

### Planning sessions

- [x] Tenancy and roles model
- [x] Scoping and applicability model
- [x] Policy library structure
- [x] Inventory data model
- [x] Intake and triage logic
- [x] AI and ADMT risk assessment methodology and output format
- [x] Technology stack and agent architecture
- [x] Regulatory update and notification planning, with the Colorado update from SB 24-205 to SB 26-189 as its first worked example (C1)

### Conflicts to resolve

Found while folding the briefs in on 2026-10-15. Where the briefs disagree with each other or with an earlier decision, this document keeps the earlier wording and marks the spot with the conflict ID.

- [x] **C1 Which Colorado AI law.** Session 2 kept "Colorado AI Act" in this document until regulatory update planning. But sessions 5 and 6 built the Colorado ADMT triage rule and obligations row on SB 26-189, and Ridgeline's expected result relies on SB 26-189's ECOA and FCRA notice overlay. The original Act's deployer impact-assessment and risk-program duties do not exist under SB 26-189, which applies from Jan 1, 2027. Resolved 2026-10-18: switch now to SB 26-189 as current law, and keep the original Act (SB 24-205) as a historical content pack that drives the regulatory update demo. Both pass CNT-01 against enacted text before content work.
- [x] **C2 ISO/IEC 42001 approach.** ISO is still parked pending license research, yet session 3 decided the CRI Profile follows "the same approach as ISO/IEC 42001": local import only, cited by ID. Resolved 2026-10-18: confirmed for ISO; licensed full-text import logged under Designed for, built later.
- [x] **C3 Regulation set grew.** The two-tier set confirmed on 2026-10-08 did not include the Colorado Privacy Act, California FEHA automated-decision rules, Illinois HB 3773 and the AI Video Interview Act, federal anti-discrimination law, NIST AI 600-1, MITRE ATLAS or the OWASP Top 10 for Agentic Applications. I placed the laws in the applicability-and-citation tier, but triage already runs a Colorado Privacy Act assessment and employment notice checks, which go beyond citation. Each also adds verification work under CNT-01. Resolved 2026-10-18: accepted in the tiers placed; future additions are flagged as potential scope creep.
- [x] **C4 Credit and marketing add features.** The v1 boundary says credit and marketing add no new features. The briefs need several: separating GLBA-exempt card data from other data, the credit and marketing intake branches, and the GDPR DPIA and ePrivacy path for Lumen. Separately, the scenario table lists EU AI Act transparency for AI-generated content for Lumen, but no triage rule or obligations row covers it. Resolved 2026-10-18: accepted as v1 features, treated as reasonable early pivots; the EU AI Act transparency item was dropped from Lumen, since Article 50's deployer duties cover deepfakes and public-interest text, not targeted ad copy.
- [x] **C5 Two definitions of risk level for routing.** Session 1 routes approval by category (high means ADMT for a significant decision, or high-risk AI). Session 6 maps the scored inherent risk onto the same routing. They can disagree, for example ADMT scored moderate. Resolved 2026-10-18: the category sets a floor at triage and the inherent risk score can only raise it (see routing above).

## Decision log

| Date | Decision |
| --- | --- |
| 2026-10-18 | Session 8: per-law content packs with supersession maps; signed bundles in v1 (accepted scope growth); per-tenant adoption after a side-by-side dry run; risk-tiered reassessment windows of 30, 60 and 90 days |
| 2026-10-18 | Session 8: deferral past the effective date allowed but recorded, visible and backed by DPO risk acceptance, with escalating reminders from 12 months out |
| 2026-10-18 | Session 8: Colorado demo keeps the date-only SB 25B-004 step and frames the SB 24-205 work as a readiness assessment, since that law never took effect |
| 2026-10-18 | Session 8: recorded self-verification of content is acceptable while Tim is the only maintainer, stated openly in the documentation |
| 2026-10-18 | C5: approval routing uses the triage category as a floor; the inherent risk score can raise it but never lower it; tenant-configurable default |
| 2026-10-18 | EU AI Act transparency dropped from the Lumen scenario: Article 50's deployer duties do not reach targeted ad copy; Article 50 checks designed for, built later |
| 2026-10-18 | C1: Colorado content switches to SB 26-189; the original Colorado AI Act (SB 24-205) stays as a historical pack that powers the regulatory update demo |
| 2026-10-18 | C2: ISO/IEC 42001 is cited by clause ID with OpenDPO summaries, no ISO text shipped; licensed full-text import designed for, built later |
| 2026-10-18 | C3 and C4: planning-stage scope growth accepted as reasonable early pivots; later additions are flagged as potential scope creep before adoption |
| 2026-10-18 | Deployment model: self-hosted only; multi-tenancy kept so one install serves a single organization or a consultancy with several clients |
| 2026-10-15 | Session 7: stack is Python with FastAPI, PostgreSQL with row-level security and pgvector, React in TypeScript with schema-driven forms, Keycloak from v1, Rego (Open Policy Agent) for roles, segregation of duties and triage rules, YAML content packs, Anthropic API behind a provider interface, Docker Compose |
| 2026-10-15 | Session 7: agents read and write drafts only; citations must resolve; uploads are untrusted; evaluation suite runs in CI with published results |
| 2026-10-15 | Session 7: hash-chained audit log, verified daily and before every export, with alerts to tenant admin, DPO and auditors on a break |
| 2026-10-15 | Session 7: v1 is run-it-yourself plus a recorded demo; a cached, nightly-reset hosted sandbox comes after v1 |
| 2026-10-15 | Guiding principle: favor the stronger story over the faster path; companion documentation, walkthrough deck and recorded demo script planned |
| 2026-10-15 | Session 6: assessment built on CPPA section 7152's nine elements; one assessment yields an internal assessment and a regulator-ready report; DPIA shares the form with GDPR sections added |
| 2026-10-15 | Session 6: 5-by-5 risk scale on NIST SP 800-30 levels, with NIST PRAM framing for severity; scale is replaceable per tenant |
| 2026-10-15 | Session 6: unified harm taxonomy across CPPA, Colorado Privacy Act Rules, Virginia-model laws and NIST PRAM, verified with Tim's participation; AI security sources add NIST AI 600-1, MITRE ATLAS and OWASP Top 10 for Agentic Applications |
| 2026-10-15 | Session 6: DPO can override at every risk level as a formal risk acceptance; review defaults annual, two-year and three-year by risk, adjustable under a hard maximum from regulatory content |
| 2026-10-15 | Session 5: deterministic triage rules decide, the agent explains; nine core intake questions kept; "not sure" goes to an analyst first; submitters confirm low-confidence and trigger-relevant pre-fills; description guidance; go-live date and stage captured |
| 2026-10-15 | Session 4: seven-entity inventory around the processing activity; origin field; vendor information requests and model cards with a fast track; multi-select data categories with custom entries; four-value AI role scale plus a human review field; tenant and project consumer counts kept separate; transfers optional |
| 2026-10-15 | Session 2: guided plain-language scoping; US and EU on a jurisdiction-agnostic design; volume bands on legal thresholds; every state collected; content verification gate on primary sources; Colorado rewrite held for regulatory update planning |
| 2026-10-15 | Credit demo tenant is Ridgeline Card Services, a fictional for-profit consumer card issuer, replacing the credit union |
| 2026-10-14 | Session 3: seventeen OpenDPO-authored policy templates, seven fully written including the external privacy notice; research open templates first, reuse only CC BY-compatible text; tenant copies with opt-in diffs; sixth position type, conditional permission; peg to Privacy Framework 1.0 |
| 2026-10-14 | No CRI Profile text in the repo (CC BY-NC-ND 4.0); diagnostic statement IDs with our own summaries, local import for rights holders. Supersedes the 2026-10-08 CRI deferral |
| 2026-10-08 | Session 1: workspace, tenant and membership levels; eight default roles; approval routed by risk with analyst provisional approval; three approval presets; internal review notes and clarification requests; role holders treated alike, including outsourced DPOs; demo tenants Harbor Staffing and Lumen Outfitters |
| 2026-10-08 | Repo license: Apache 2.0 for code, CC BY 4.0 for templates and content |
| 2026-10-08 | v1 policy templates cover the policies CSF 2.0 and the Privacy Framework require; CRI Profile deferred |
| 2026-10-08 | Regulatory content in two tiers: full mappings for core AI and privacy rules, applicability and citation only for scenario-specific laws |
| 2026-10-08 | Resume screening built end to end first; credit and marketing scenarios add no new features |
| 2026-10-08 | Project identity and mission confirmed |
| 2026-10-08 | OpenDPO is positioned as a proof of concept: no legal advice, no replacement for qualified human review, stated in docs, app and exports |
| 2026-10-08 | AI assessment grounded in NIST AI RMF, OWASP, ISO/IEC 42001 and privacy principles; ISO included only after license-term research, and never distributed |
| 2026-10-08 | v1 headline shifts from DPIA to AI and ADMT risk assessment on a shared engine; DPIA template rides on it |
| 2026-10-08 | Unsettled AI rules treated as a feature: v1 demonstrates human-reviewed regulatory content updates |
| 2026-10-08 | The project assesses itself: its own DPIA and AI risk assessment, produced with the platform, are published in the repo |
| 2026-10-08 | Working name changed to OpenDPO (PrivAttest GitHub handle taken); repo under Tim's own account |
| 2026-10-08 | Requirements tracked in this living document |
| 2026-10-08 | Scope reined in: one thin vertical slice for v1, full vision designed for in the data model |
| 2026-10-08 | Platform must serve a single org or a consultant managing several clients |
| 2026-10-08 | Policy template library may be open-sourced; orgs can import their own policies |
| 2026-10-08 | Crosswalks are human-reviewable and editable; agent-proposed changes need approval |
| 2026-10-08 | Publishing publicly is acceptable because comparable commercial products already exist |
| 2026-10-08 | Project goal is a portfolio piece showing privacy, cybersecurity and AI leadership skills |
| 2026-10-08 | Project pivoted from a crosswalk tool to an AI privacy-office platform with human-in-the-loop workflows |
