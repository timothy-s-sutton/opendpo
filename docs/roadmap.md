# Roadmap

OpenDPO ships in two steps: a preview that runs one complete workflow end to end, then v1. Requirement IDs refer to [requirements.md](requirements.md).

## Preview: the Harbor Staffing walkthrough

One fictional client tenant, Harbor Staffing, takes an AI resume-screening tool from intake to an approved, exported AI and ADMT risk assessment.

| Area | In the preview | Requirements |
| --- | --- | --- |
| Identity and roles | Keycloak local accounts, all eight roles seeded, standard approval preset, segregation of duties in Rego | PLT-01 to PLT-06, SOD-1 to SOD-6 |
| Audit trail | Hash-chained log, verification command, JSON export | PLT-40 to PLT-42 |
| Content | Three laws verified against primary text: the CCPA Regulations on risk assessments and ADMT, Colorado SB 26-189, NYC Local Law 144. Other research stays visibly marked unverified and the rules engine refuses it | CNT-01, CNT-02, CNT-04 |
| Intake and triage | Nine core questions and the AI decision branch; deterministic triage with cited explanations; analyst confirmation | WF-01 to WF-08 |
| Assessment | Agent draft on the CCPA Regulations section 7152 elements, reviewer edits, 5-by-5 risk scale, two-person approval for high risk, internal and regulator-ready exports | WF-10 to WF-16, WF-19 to WF-21 |
| Evaluation | Triage test fixtures run in continuous integration | ARC-04 (partial) |
| Packaging | One Docker Compose command with seeded demo data | Goal 1 (partial) |

Deferred to v1: the Ridgeline Card Services and Lumen Outfitters tenants, the full scoping questionnaire (Harbor's answers are pre-filled), the Colorado regulatory update demo, signed content bundles, policy import, vendor information requests, and most policy templates.

## v1

| Phase | Adds |
| --- | --- |
| Breadth | Ridgeline and Lumen tenants, credit and marketing intake branches, GDPR DPIA sections, the remaining verified law packs, full evaluation suite |
| Regulatory updates | Versioned content packs with supersession maps, signed bundles, per-tenant adoption after a dry run, reassessment flags and notifications; the Colorado SB 24-205 to SB 26-189 demo |
| Policy library | Seventeen templates, seven fully written; policy import with human-confirmed positions |
| Release | Full scoping questionnaire, documentation site, and the project's own DPIA and AI risk assessment produced with OpenDPO |

## Later

SSO and SCIM, SIEM forwarding, PIA, TIA and LIA templates, DSAR and breach workflows, more US state and non-US privacy laws as content packs, automated regulatory monitoring, and a hosted read-only sandbox.
