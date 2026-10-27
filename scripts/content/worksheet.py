"""Render a pack as a verification worksheet (markdown): rules in plain English, then provisions."""
import sys
from pathlib import Path

import yaml

FACTS = {}
SHORT = "--ids" in sys.argv  # name questions by id in rule conditions; their text is in the Questions section


def cond(c, depth=0):
    if "all" in c:
        lead = "both of" if len(c["all"]) == 2 else "all of"
        return f"{lead}: " + "; and ".join(cond(x, depth + 1) for x in c["all"])
    if "any" in c:
        same = {x.get("fact") for x in c["any"]}
        if len(same) == 1 and None not in same and all("contains" in x for x in c["any"]):
            f = FACTS.get(c["any"][0]["fact"], c["any"][0]["fact"])
            return f"{f} includes any of [{', '.join(x['contains'] for x in c['any'])}]"
        return "at least one of: (" + ", or ".join(cond(x, depth + 1) for x in c["any"]) + ")"
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


INTROS = {
    "us-ca-ccpa-regs-2025": "The text was copied by software from the consolidated regulations PDF you supplied, "
    "not retyped, and software confirmed every quote also appears in the approved rulemaking text, except § 7155(b), "
    "where the consolidated text fills in OAL's effective date. Spot-check against the page shown and check each "
    "summary is fair.",
    "us-ca-ccpa-statute": "These definitions come from the authenticated Civil Code § 1798.140 PDF you supplied "
    "(as amended by AB 1170, effective January 1, 2026). Software copied the text; it was not retyped. Only the "
    "definitions the questions above rely on are included. Spot-check against the page shown and check each "
    "summary is fair.",
    "us-co-sb26-189": "These provisions come from the signed act you supplied (SB 26-189, approved May 14, 2026). "
    "That PDF is a scan, so its text layer is OCR. Software copied the OCR text, not retyped, then applied only the "
    "listed corrections where OCR split or merged words or misread a paragraph number; each provision shows the "
    "corrections made to it. Check those against the page image. Capital letters are kept as printed (in the act "
    "they mark new statutory text). Only the provisions the rules and questions use are included; section 1702 "
    "(developer duties, outside the deployer-only preview), 1704(5)-(7) and (9), 1705(2)-(3), 1706, 1707, "
    "1708(3)(c)-(6) and 1709 are not.",
    "us-nyc-ll144": "These provisions come from the two PDFs you supplied: the Council's legislation text of "
    "Int. No. 1894-A (Local Law 144 of 2021) and DCWP's notice of adoption of 6 RCNY §§ 5-300 to 5-304. Both have real "
    "text layers; software copied the text, not retyped. Legistar repeats each page's last line at the top of the next "
    "page, and the copy drops the repeat. The DCWP rule's worked examples and tables are left out. Spot-check against "
    "the page shown and check each summary is fair.",
}


def main(path):
    p = yaml.safe_load(open(path, encoding="utf-8"))
    facts = {f["id"]: f for f in p.get("facts", [])}
    derived = {}
    for r in p.get("rules", []):
        if "set_fact" in r["result"]:
            derived.setdefault(r["result"]["set_fact"], []).append(r["id"])
    for f in facts.values():
        FACTS[f["id"]] = f"`{f['id']}`" if SHORT else f"“{f['question'].rstrip('?')}”"
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
    out = [] if not p.get("rules") else ["## Rules: is the reading of the law correct?", "",
           "Tick a rule when its conditions and conclusion correctly apply the provisions it cites. "
           "Comment on anything you would change; I will update the rule and ask again."
           + (" Conditions name questions by id; each question's full text is in the Questions section." if SHORT else ""), ""]
    for r in p.get("rules", []):
        out += [f"### {r['id']}: {r['title']}", "",
                f"- **Fires when:** {cond(r['when'])}",
                f"- **Concludes:** `{yaml.safe_dump(r['result'], default_flow_style=True).strip()}`",
                f"- **Cites:** {', '.join(r['provisions'])}"
                + (f"; definitions behind its questions: {', '.join(c for c in citations(r) if c not in r['provisions'])}"
                   if len(citations(r)) > len(r['provisions']) else ""),
                f"- **Explanation shown to users:** {r['explanation']}", "",
                f"- [ ] Reading of the law is correct ({r['id']})", ""]
    out += [] if not p.get("facts") else ["## Questions: does each question match the definition behind it?", "",
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
    intro = INTROS.get(p["id"], "The text was copied by software from the source PDF, not retyped. "
                       "Spot-check against the page shown and check each summary is fair.")
    out += [f"## {'Provisions' if p.get('rules') else p['title']}: does the quoted text match the source?", "", intro, ""]
    side = Path(path).with_name("ocr-corrections.yaml")
    fixes = (yaml.safe_load(side.read_text(encoding="utf-8")) or {}) if side.is_file() else {}
    for pr in p["provisions"]:
        out += [f"### {pr['citation']}", "",
                f"{pr['location']} · ID `{pr['id']}`", "",
                f"> {pr['text']}", ""]
        if pr["id"] in fixes:
            out += ["**OCR corrections:** " + "; ".join(f"“{c['scanned']}” → “{c['printed']}”" for c in fixes[pr["id"]]), ""]
        out += [f"**OpenDPO summary:** {pr['summary']}", "",
                f"- [ ] Text matches the source and the summary is fair ({pr['id']})", ""]
    print("\n".join(out))


if __name__ == "__main__":
    main(next(a for a in sys.argv[1:] if not a.startswith("--")))
