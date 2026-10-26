# Regulatory content

Content packs are YAML files, one pack per law or framework. Nothing here enters the rules engine until it passes the verification gate (CNT-01): each rule records its primary citation, the date it was verified against primary text, and who verified it. Law firm and vendor summaries may be used to find provisions, never as the citation of record.

OpenDPO has one maintainer, who authors and verifies this content. Each rule records that the verification was done by the author.

Packs carry an as-of date. Laws change; verify before relying on any content here.

## Intake layout

`intake.yaml` places questions on the one intake form (WF-01, WF-02): nine core questions, then a section per law that shows only when the core answers make it relevant. A pack question is named by its fact id; its wording, options and definitions come from the pack, so changing them still needs a sign-off. The API turns the layout into a JSON Schema at `/api/tenants/<id>/intake/form`, with each question's definitions attached. The API refuses to start if a pack's intake question is placed nowhere or a condition refers to a later question.
