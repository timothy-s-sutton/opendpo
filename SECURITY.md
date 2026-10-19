# Security policy

OpenDPO is a proof of concept and has not been independently security tested. Do not expose a demo instance to the internet or load real personal data into it.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's "Report a vulnerability" option on this repository's Security tab, not as a public issue. Include steps to reproduce and the affected version or commit.

## Security design

The threat model is in [docs/threat-model.md](docs/threat-model.md). Key controls: tenant isolation enforced by PostgreSQL row-level security; roles and segregation of duties enforced by Open Policy Agent; an agent identity that cannot approve; uploaded documents treated as untrusted data; and a hash-chained, tamper-evident audit log.
