"""Render a pack as a verification worksheet (markdown): rules in plain English, then provisions."""
import sys

import yaml

FACTS = {
    "scope.ccpa_applies": "the CCPA applies to the tenant (set in scoping)",
    "data.sells_or_shares": "the project sells or shares personal information",
    "data.sensitive": "the project processes sensitive personal information",
    "data.sensitive_hr_admin_only": "sensitive data is used only for the listed workforce administration purposes",
    "ai.role": "the AI's role in the decision",
    "ai.human_review": "the human review of the AI output",
    "ai.infers_traits_from_observation": "the AI infers traits from systematic observation",
    "ai.infers_from_sensitive_location": "the AI infers traits from presence in a sensitive location",
    "ai.trains_admt_for_significant_decisions": "the data is used to train ADMT for significant decisions",
    "ai.trains_identity_or_biometric": "the data is used to train identity, facial, emotion or biometric technology",
    "decision.domain": "the decision domain",
    "decision.employment_type": "the type of employment decision",
    "subjects": "the people whose data is processed",
    "cppa.admt": "the system is ADMT under the CPPA (from CPPA-CLASS-ADMT)",
    "cppa.significant_decision": "the decision is a significant decision (from CPPA-CLASS-SIGNIFICANT)",
}


def cond(c, depth=0):
    if "all" in c:
        return "all of: " + "; ".join(cond(x, depth + 1) for x in c["all"])
    if "any" in c:
        return "any of (" + " / ".join(cond(x, depth + 1) for x in c["any"]) + ")"
    if "not" in c:
        return "NOT " + cond(c["not"], depth + 1)
    f = FACTS.get(c["fact"], c["fact"])
    if "equals" in c:
        v = c["equals"]
        return f if v is True else f"{f} is false" if v is False else f"{f} is {v}"
    if "in" in c:
        return f"{f} is one of [{', '.join(map(str, c['in']))}]"
    if "contains" in c:
        return f"{f} include {c['contains']}"
    return f"{f} is at least {c['at_least']}"


def main(path):
    p = yaml.safe_load(open(path, encoding="utf-8"))
    out = ["## Rules: is the reading of the law correct?", "",
           "Tick a rule when its conditions and conclusion correctly apply the provisions it cites. "
           "Comment on anything you would change; I will update the rule and ask again.", ""]
    for r in p["rules"]:
        out += [f"### {r['id']}: {r['title']}", "",
                f"- **Fires when:** {cond(r['when'])}",
                f"- **Concludes:** `{yaml.safe_dump(r['result'], default_flow_style=True).strip()}`",
                f"- **Cites:** {', '.join(r['provisions'])}",
                f"- **Explanation shown to users:** {r['explanation']}", "",
                f"- [ ] Reading of the law is correct ({r['id']})", ""]
    out += ["## Provisions: does the quoted text match the source?", "",
            "The text was copied by software from the PDF you supplied, not retyped. Spot-check each against "
            "the page shown, and check the summary is fair.", ""]
    for pr in p["provisions"]:
        out += [f"### {pr['citation']}", "",
                f"{pr['location']} · ID `{pr['id']}`", "",
                f"> {pr['text']}", "",
                f"**OpenDPO summary:** {pr['summary']}", "",
                f"- [ ] Text matches the source and the summary is fair ({pr['id']})", ""]
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1])
