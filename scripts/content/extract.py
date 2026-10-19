"""Pull verbatim provision text out of a pdftotext -layout dump.

Used while drafting packs: it copies text from the source instead of retyping it.
Page headers and footers are dropped and whitespace is collapsed, which does not
change a provision's fingerprint (see api/opendpo/content.py).
"""
import re
import sys

FOOTER = re.compile(r"^(CA PRIVACY PROTECTION AGENCY|\(CCPA Updates|Page \d+ of \d+)")


def clean_lines(path):
    out = []
    page = 1
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^Page (\d+) of \d+", line.strip())
        if m:
            page = int(m.group(1)) + 1
        if FOOTER.match(line.strip()):
            continue
        out.append((page, line.rstrip("\n")))
    return out


def between(lines, start, end, include_end=False, after=None):
    """Text from the line containing `start` up to (not including) the line containing `end`,
    searching only after the line containing `after` when given."""
    text, pages, on = [], set(), False
    armed = after is None
    for page, line in lines:
        if not armed:
            armed = after in line
            continue
        if not on and start in line:
            on = True
        if on and end in line and (text or start not in line):
            if include_end:
                text.append(line)
                pages.add(page)
            break
        if on:
            text.append(line)
            pages.add(page)
    if not text:
        raise SystemExit(f"start marker not found: {start!r}")
    joined = ""
    for raw in text:
        part = " ".join(raw.split())
        if not part:
            continue
        # A hyphen at the end of a line joins the word across the break ("non-" + "medical").
        if joined.endswith("-") and len(joined) > 1 and joined[-2].isalpha():
            joined += part
        else:
            joined = f"{joined} {part}" if joined else part
    return joined, sorted(pages)


if __name__ == "__main__":
    lines = clean_lines(sys.argv[1])
    print(between(lines, sys.argv[2], sys.argv[3]))
