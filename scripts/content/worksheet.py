"""Render a pack as a verification worksheet (markdown): rules in plain English, then provisions."""
import sys

import yaml

FACTS = {}


def cond(c, depth=0):
    if "all" in c:
        return "all of: " + "; ".join(cond(x, depth + 1) for x in c["all"])
    if "any" in c:
        same = {x.get("fact") for x in c["any"]}
        if len(same) == 1 and None not in same and all("contains" in x for x in c["any"]):
            f = FACTS.get(c["any"][0]["fact"], c["any"][0]["fact"])
            return f"{f} includes any of [{', '.join(x['contains'] for x in c['any'])}]"
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
        return f"{f} includes {c['contains']}"
    return f"{f} is at least {c['at_least']}"


def main(path):
    p = yaml.safe_load(open(path, encoding="utf-8"))
    facts = {f["id"]: f for f in p.get("facts", [])}
    derived = {}
    for r in p["rules"]:
        if "set_fact" in r["result"]:
            derived.setdefault(r["result"]["set_fact"], []).append(r["id"])
    for f in facts.values():
        FACTS[f["id"]] = f"“{f['question'].rstrip('?')}”"
    for fid, rids in derived.items():
        FACTS[fid] = f"{fid} (from {' or '.join(rids)})"

    def leaves(c):
        if "fact" in c:
            return [c["fact"]]
        kids = c.get("all", []) + c.get("any", []) + ([c["not"]] if "not" in c else [])
        return [x for k in kids for x in leaves(k)]

    def citations(r):
        out = list(r["provisions"])
        for fid in sorted(set(leaves(r["when"]))):
            for pid in facts.get(fid, {}).get("defined_by", []):
                if pid not in out:
                    out.append(pid)
        return out
    out = ["## Rules: is the reading of the law correct?", "",
           "Tick a rule when its conditions and conclusion correctly apply the provisions it cites. "
           "Comment on anything you would change; I will update the rule and ask again.", ""]
    for r in p["rules"]:
        out += [f"### {r['id']}: {r['title']}", "",
                f"- **Fires when:** {cond(r['when'])}",
                f"- **Concludes:** `{yaml.safe_dump(r['result'], default_flow_style=True).strip()}`",
                f"- **Cites:** {', '.join(r['provisions'])}"
                + (f"; definitions behind its questions: {', '.join(c for c in citations(r) if c not in r['provisions'])}"
                   if len(citations(r)) > len(r['provisions']) else ""),
                f"- **Explanation shown to users:** {r['explanation']}", "",
                f"- [ ] Reading of the law is correct ({r['id']})", ""]
    out += ["## Questions: does each question match the definition behind it?", "",
            "Rules only test these answers, so each question has to capture its definition faithfully. "
            "The definitions listed are shown beside the question in the app and cited in every explanation.", ""]
    for f in p.get("facts", []):
        opts = "".join(f"\n    - `{o['value']}`: {o['label']}" for o in f.get("options") or [])
        out += [f"### {f['id']}", "",
                f"- **Asks:** {f['question']} ({f['type']}, asked in {f.get('asked_in', 'intake')})" + opts,
                f"- **Defined by:** {', '.join(f['defined_by']) if f.get('defined_by') else 'none yet'}"]
        if f.get("help"):
            out.append(f"- **Note:** {f['help']}")
        if f.get("pending"):
            out.append(f"- **Pending:** {f['pending']}")
        out += ["", f"- [ ] Question captures its definition ({f['id']})", ""]
    out += ["## Provisions: does the quoted text match the source?", "",
            "The text was copied by software from the consolidated regulations PDF you supplied, not retyped, "
            "and software confirmed every quote also appears in the approved rulemaking text, except § 7155(b), "
            "where the consolidated text fills in OAL's effective date. Spot-check against the page shown and "
            "check each summary is fair.", ""]
    for pr in p["provisions"]:
        out += [f"### {pr['citation']}", "",
                f"{pr['location']} · ID `{pr['id']}`", "",
                f"> {pr['text']}", "",
                f"**OpenDPO summary:** {pr['summary']}", "",
                f"- [ ] Text matches the source and the summary is fair ({pr['id']})", ""]
    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1])
