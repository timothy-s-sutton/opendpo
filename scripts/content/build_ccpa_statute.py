"""Draft the CCPA statute definitions pack from Civil Code section 1798.140.

    pdftotext -layout CIV_1798.140.pdf civ_1798_140.txt
    python build_ccpa_statute.py civ_1798_140.txt ../../content/packs/us-ca-ccpa-statute/pack.yaml

The source of record is the authenticated text from California Legislative Information
(leginfo.legislature.ca.gov), as amended by Stats. 2025, Ch. 67 (AB 1170), effective
January 1, 2026. Text is copied, never retyped. Only the definitions that the
CCPA Regulations pack's questions depend on are included.
"""
import sys

import yaml

SRC = "ca-civ-1798-140"
CIT = "Cal. Civ. Code § 1798.140"

# id suffix, subdivision, start marker, end marker, OpenDPO summary
PROVISIONS = [
    ("d", "(d)", "(d) “Business” means:", "(e) “Business purpose” means",
     "A business is a for-profit entity that collects consumers' personal information, determines why and how it is processed, does business in California, and meets one threshold: more than $25 million in annual gross revenue (as adjusted), buying, selling or sharing the personal information of 100,000 or more consumers or households a year, or deriving half or more of its revenue from selling or sharing it. Commonly branded affiliates it controls, qualifying joint ventures, and entities that voluntarily certify to the CPPA also count."),
    ("i", "(i)", "(i) “Consumer” means a natural person", "(j) (1) “Contractor” means",
     "A consumer is any natural person who is a California resident, however identified."),
    ("k", "(k)", "(k) “Cross-context behavioral advertising” means", "(l) “Dark pattern” means",
     "Cross-context behavioral advertising is targeting ads to a consumer based on personal information from their activity across other businesses' websites, apps or services."),
    ("ad", "(ad)", "(ad) (1) “Sell,”", "(ae) “Sensitive personal information” means:",
     "Selling is disclosing or making available a consumer's personal information to a third party for money or other valuable consideration. It excludes disclosures the consumer directs, opt-out signals, and transfers in a merger, acquisition or bankruptcy."),
    ("ah", "(ah)", "(ah) (1) “Share,”", "(ai) “Third party” means",
     "Sharing is disclosing or making available a consumer's personal information to a third party for cross-context behavioral advertising, paid or not. It has the same exclusions as selling."),
    ("ai", "(ai)", "(ai) “Third party” means", "(aj) “Unique identifier”",
     "A third party is anyone other than the business the consumer intentionally interacts with, its service providers and its contractors."),
]


def main(src: str, out: str) -> None:
    raw = open(src, encoding="utf-8").read()
    pages = raw.split("\f")
    flat = " ".join(raw.split())
    provisions = []
    for sid, sub, start, end, summary in PROVISIONS:
        a = flat.index(start)
        b = flat.index(end, a)
        text = flat[a:b].strip()
        head = " ".join(start.split()[:3])
        page = next(i + 1 for i, p in enumerate(pages) if head in " ".join(p.split()))
        provisions.append({"id": f"ccpa-1798-140-{sid}", "citation": f"{CIT}{sub}", "source": SRC,
                           "location": f"Section 1798.140, p. {page}", "effective_from": "2026-01-01",
                           "text": text, "summary": summary})
    pack = {
        "id": "us-ca-ccpa-statute", "title": "California Consumer Privacy Act: definitions (Civil Code section 1798.140)",
        "jurisdiction": "US-CA", "version": "0.1.0", "lifecycle": "effective", "as_of": "2026-10-26",
        "sources": [{"id": SRC, "title": "California Civil Code section 1798.140 (as amended by Stats. 2025, Ch. 67, AB 1170)",
                     "publisher": "California Legislative Information", "primary": True, "retrieved_on": "2026-10-26",
                     "url": "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1798.140"}],
        "provisions": provisions,
    }
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(pack, f, sort_keys=False, allow_unicode=True, width=110)


if __name__ == "__main__":
    main(*sys.argv[1:3])
