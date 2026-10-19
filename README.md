# OpenDPO

**An open-source reference implementation of a human-governed AI privacy office. Rules decide, the AI drafts and explains, a named human approves.**

> **Intended use.** OpenDPO is a proof of concept built by a privacy practitioner, not by lawyers. It provides no legal advice and is not a substitute for review and decisions by qualified privacy, legal and compliance professionals. Every AI output is a draft for qualified human review. Demo data is fictional; do not load real personal data into a demo instance. Regulatory content records its as-of date and source, and rules change, so verify before relying on it.

## Why this exists

Privacy teams are being asked to assess AI systems under fast-moving rules, such as the CPPA's risk assessment and automated decisionmaking technology (ADMT) regulations and Colorado's SB 26-189. AI can carry much of the analytical load, but only if every conclusion stays traceable to the law, the organization's own policy, and a named person who approved it.

OpenDPO shows one way to do that:

| Principle | How OpenDPO enforces it |
| --- | --- |
| **Rules decide, the agent explains** | Whether a law applies, and which assessments are triggered, comes from deterministic rules written in Rego (Open Policy Agent). The same answers always give the same result. The model never decides applicability; it explains the result in plain language with citations. |
| **Humans own every decision** | The agent acts under a system identity that cannot hold a role, so it can never approve. Approvals, mapping changes and policy changes are endpoints the agent cannot call. |
| **Everything is traceable** | Every finding cites a stored policy position or regulatory clause. Citations that do not resolve fail validation before a person sees the draft. Each output records the content and policy versions it used. |
| **Verified content only** | No rule enters the rules engine until it has been checked against primary text (statute, regulation or official publication), with the citation, date and verifier recorded. Law firm and vendor summaries are for discovery only. |
| **Tamper-evident by default** | Every agent output, human edit and approval is written to an append-only, hash-chained audit log that is verified daily and before every export. |

## What it does

The first workflow is an **AI and ADMT risk assessment**, built on the nine content elements of CPPA regulation section 7152:

1. A business owner submits a project through a short, branching intake form.
2. The rules engine decides which assessments and obligations apply, and the agent explains why, with citations.
3. A privacy analyst confirms the triage.
4. The agent drafts the assessment from the inventory, the organization's policy positions and verified regulatory content.
5. Reviewers edit; every edit is logged against the agent's original.
6. Approval routes by risk under segregation-of-duties rules. High risk needs two distinct approvers.
7. One assessment produces a full internal assessment and a regulator-ready report.

The demo runs a fictional consultant workspace. Its first client tenant, **Harbor Staffing**, uses AI to screen resumes.

## Status

| Stage | Contents | Status |
| --- | --- | --- |
| Design | [Requirements](docs/requirements.md), [architecture](docs/architecture.md), [threat model](docs/threat-model.md), [roadmap](docs/roadmap.md) | Published |
| Preview | Harbor Staffing walkthrough, end to end, on three verified laws | In progress |
| v1 | Three demo tenants, regulatory content updates, the project's own self-assessment | Planned |

## Architecture at a glance

Python (FastAPI), PostgreSQL with row-level security, React in TypeScript with schema-driven forms, Keycloak for identity, Open Policy Agent for roles, segregation of duties and triage rules, YAML content packs, and the Anthropic API behind a provider interface. Everything runs from one Docker Compose setup. See [docs/architecture.md](docs/architecture.md).

## Licenses

- Code: [Apache License 2.0](LICENSE)
- Policy templates, regulatory content packs and documentation: [CC BY 4.0](LICENSE-CONTENT.md)

Third-party standards are cited by identifier with OpenDPO's own summaries where their licenses do not allow redistribution (for example ISO/IEC 42001 and the CRI Profile). See [NOTICE](NOTICE).

## Maintainer

OpenDPO has one maintainer, Tim Sutton, who both authors and verifies its regulatory content. Each rule records this. A second reviewer will be added once the project has contributors.
