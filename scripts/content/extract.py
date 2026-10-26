"""Pull verbatim provision text out of a pdftotext -layout dump.

Used while drafting packs: it copies text from the source instead of retyping it.
Page headers and footers are dropped and whitespace is collapsed, which does not
change a provision's fingerprint (see api/opendpo/content.py).
"""
import re
import sys

FOOTER = re.compile(r"^(CA PRIVACY PROTECTION AGENCY|\(CCPA Updates|Page \d+ of \d+$|CPPA$)")


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
            armed = after in line and "...." not in line  # skip the table of contents
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


def flatten(path, drop=None, carryover=False):
    """The whole of a pdftotext -layout dump as one whitespace-collapsed string, with a
    character offset -> page lookup. `drop` is a regex for header and footer lines.
    `carryover` drops the first body line of a page when it repeats the last body line of
    the page before (Legistar prints that line twice across a page break)."""
    pages = open(path, encoding="utf-8").read().split("\f")
    parts, starts, last = [], [], None
    for n, page in enumerate(pages, start=1):
        body = [ln for ln in page.split("\n") if ln.strip() and not (drop and drop.search(ln.strip()))]
        if carryover and body and last is not None and " ".join(body[0].split()) == last:
            body = body[1:]
        if body:
            last = " ".join(body[-1].split())
        starts.append((sum(len(p) + 1 for p in parts), n))
        joined = ""
        for raw in body:
            part = " ".join(raw.split())
            # A hyphen at the end of a line joins the word across the break ("computer-" + "based").
            if joined.endswith("-") and len(joined) > 1 and joined[-2].isalpha() and part[:1].isalpha():
                joined += part
            else:
                joined = f"{joined} {part}" if joined else part
        parts.append(joined)
    flat = " ".join(parts)
    return flat, starts


def page_at(starts, offset):
    page = 1
    for start, n in starts:
        if start <= offset:
            page = n
    return page


def cut(flat, starts, start, end, cursor=0, include_end=False):
    """Text from `start` up to `end` (both searched from `cursor`), its pages and the new cursor."""
    a = flat.index(start, cursor)
    b = flat.index(end, a + len(start))
    if include_end:
        b += len(end)
    text = flat[a:b].strip()
    pages = sorted({page_at(starts, a), page_at(starts, a + len(text) - 1)})
    return text, pages, b


def correct(text, fixes):
    """Apply listed OCR corrections; return the text and the corrections that changed it.
    Each correction is a pair (as scanned, as printed) checked by eye against the page image."""
    applied = []
    for wrong, right in fixes:
        if wrong in text:
            text = text.replace(wrong, right)
            applied.append({"scanned": wrong, "printed": right})
    return text, applied
