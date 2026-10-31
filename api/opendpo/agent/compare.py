"""Compare models on the same assessment, side by side, without saving anything.

Run inside the API container once ANTHROPIC_API_KEY is set:

    docker compose exec api python -m opendpo.agent.compare --assessment <id> > compare.md

Each model drafts the same assessment from the same material. The report shows, for each:
whether the draft passed validation and in how many attempts, tokens and estimated cost,
time taken, the risk register with ratings, and every section's text.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from uuid import UUID

from .. import assessment as engine
from .. import main  # noqa: F401  (loads the API modules in order)
from .. import assessments_api
from ..db import tenant_tx
from . import drafter, providers

HARBOR = UUID("ff3e39f3-ea89-5b8d-9af6-2638c94349e3")
# US dollars per million tokens (input, output), Anthropic API standard tier, checked 2026-10-27.
PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.00, 20.00)}


def cost(model: str, usage: dict) -> float | None:
    price = next((v for k, v in PRICES.items() if model.startswith(k)), None)
    if price is None:
        return None
    return (usage.get("input_tokens", 0) * price[0] + usage.get("output_tokens", 0) * price[1]) / 1_000_000


def run(m: drafter.Material, model: str) -> dict:
    provider = providers.AnthropicProvider(model=model)
    usage_total = {"input_tokens": 0, "output_tokens": 0}

    class Counting:
        name, model = provider.name, provider.model

        def complete(self, *a, **kw):
            reply = provider.complete(*a, **kw)
            for k in usage_total:
                usage_total[k] += reply.usage.get(k, 0)
            return reply

    start = time.monotonic()
    try:
        d = drafter.draft(m, Counting())
        out = {"ok": True, "sections": d.sections, "attempts": d.attempts, "open_questions": d.open_questions,
               "problems": []}
    except drafter.DraftRejected as exc:
        out = {"ok": False, "sections": None, "attempts": 2, "open_questions": [], "problems": exc.problems,
               "raw": exc.reply.output if exc.reply else None}
    out.update(model=model, seconds=round(time.monotonic() - start), usage=usage_total,
               cost=cost(model, usage_total))
    return out


def report(results: list[dict], m: drafter.Material) -> str:
    lines = ["# Model comparison: Harbor assessment draft", "",
             "Same material, same instructions, same checks. Nothing here was saved to the assessment.", "",
             "| | " + " | ".join(r["model"] for r in results) + " |",
             "|---|" + "---|" * len(results)]

    def row(label, f):
        lines.append(f"| {label} | " + " | ".join(f(r) for r in results) + " |")
    row("Passed checks", lambda r: "yes" if r["ok"] else "no")
    row("Attempts", lambda r: str(r["attempts"]))
    row("Time", lambda r: f"{r['seconds']} s")
    row("Tokens in / out", lambda r: f"{r['usage']['input_tokens']:,} / {r['usage']['output_tokens']:,}")
    row("Estimated cost", lambda r: f"${r['cost']:.3f}" if r["cost"] is not None else "unknown")
    row("Risks / safeguards", lambda r: (f"{len(r['sections']['risks']['risks'])} / "
                                         f"{len(r['sections']['safeguards']['safeguards'])}") if r["ok"] else "-")
    row("Open questions", lambda r: str(len(r["open_questions"])))
    for r in results:
        lines += ["", f"## {r['model']}", ""]
        if not r["ok"]:
            lines += ["The draft failed validation twice and would not have been saved:", ""]
            lines += [f"- {p}" for p in r["problems"]]
            continue
        s = r["sections"]
        state = {k: v for k, v in s.items()}
        rated = {x["risk"]: x for x in engine.derive(state, m.template, m.method, "high", [])["ratings"]}
        lines += ["| Risk | Harm | Before safeguards | After |", "|---|---|---|---|"]
        for risk in s["risks"]["risks"]:
            x = rated[risk["id"]]
            lines.append(f"| {risk['id']}. {risk['title']} | {risk.get('harm') or '-'} | {x['inherent']} | "
                         f"{x['residual'] or '-'} |")
        for sid in drafter.TEXT_SECTIONS:
            lines += ["", f"### {m.template.section(sid).title}", "", s[sid]["text"]]
        lines += ["", "### Safeguards", ""]
        lines += [f"- **{g['id']}. {g['title']}** (addresses {', '.join(g['addresses'])}): {g['description']}"
                  for g in s["safeguards"]["safeguards"]]
        lines += ["", "### Decision notes", "", s["decision"]["rationale"]]
        if r["open_questions"]:
            lines += ["", "### Open questions", ""] + [f"- {q}" for q in r["open_questions"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--assessment", required=True, type=UUID)
    ap.add_argument("--tenant", type=UUID, default=HARBOR)
    ap.add_argument("--models", default="claude-sonnet-5-5,claude-haiku-5-5")
    ap.add_argument("--json", type=Path, help="also save the raw drafts here")
    args = ap.parse_args()
    with tenant_tx(args.tenant) as conn:
        m = assessments_api.build_material(conn, assessments_api.load_assessment(conn, args.assessment))
    results = [run(m, model.strip()) for model in args.models.split(",")]
    if args.json:
        args.json.write_text(json.dumps(results, indent=1, default=str))
    print(report(results, m))


if __name__ == "__main__":
    main()
