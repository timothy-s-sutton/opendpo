"""Draft the NYC automated employment decision tools pack: Local Law 144 of 2021 and the DCWP rules.

    pdftotext -layout Legislation_Text.pdf nyc_ll144.txt
    pdftotext -layout DCWP-NOA-for-Use-of-Automated-Employment-Decisionmaking-Tools-2.pdf nyc_dcwp_noa.txt
    python build_nyc_ll144.py nyc_ll144.txt nyc_dcwp_noa.txt ../../content/packs/us-nyc-ll144/pack.yaml

Sources of record: the enacted text of Int. No. 1894-A (Local Law 144 of 2021, Admin. Code
§§ 20-870 to 20-874) from the Council's Legistar, and DCWP's notice of adoption of the final
rule adding 6 RCNY §§ 5-300 to 5-304. Both PDFs have real text layers, so nothing is corrected.
Legistar repeats the last line of each page at the top of the next; the builder drops the repeat.
The DCWP rule's worked examples and tables are left out of the provisions that precede them.

Facts and rules are authored by hand in pack.yaml and are kept when this script reruns.
"""
import re
import sys
from pathlib import Path

import yaml

from extract import cut, flatten

LL = "nyc-ll144-2021"
RULE = "nyc-dcwp-aedt-rule"
CODE = "N.Y.C. Admin. Code § "
RCNY = "6 RCNY § "

LL_DROP = re.compile(r"^(The New York City Council\s+(City Hall|Page \d)|New York, NY 10007|Legislation Text$"
                     r"|File #: Int 1894-2020|powered by Legistar)")
NOA_DROP = re.compile(r"^\d{1,2}$")

# source, id, citation, start, end, OpenDPO summary
PROVISIONS = [
    (LL, "20-870-aedt", CODE + "20-870 (automated employment decision tool)",
     "Automated employment decision tool. The term", "Bias audit. The term",
     "An AEDT is a computational process derived from machine learning, statistical modeling, data analytics or "
     "artificial intelligence that issues simplified output, such as a score, classification or recommendation, used "
     "to substantially assist or replace discretionary decision making for employment decisions. Tools that do not "
     "do that, such as spam filters, firewalls, spreadsheets and databases, are excluded."),
    (LL, "20-870-bias-audit", CODE + "20-870 (bias audit)", "Bias audit. The term", "Employment decision. The term",
     "A bias audit is an impartial evaluation by an independent auditor that tests the tool's disparate impact on "
     "the EEO-1 component 1 categories (sex and race/ethnicity)."),
    (LL, "20-870-employment-decision", CODE + "20-870 (employment decision)", "Employment decision. The term",
     "§ 20-871 Requirements",
     "An employment decision means screening candidates for employment, or employees for promotion, within the city."),
    (LL, "20-871-a", CODE + "20-871(a)", "§ 20-871 Requirements", "b. Notices required.",
     "An employer or employment agency may not use an AEDT to screen for an employment decision in the city unless "
     "the tool had a bias audit within the past year and a summary of the latest audit and the tool's distribution "
     "date are public on its website before use."),
    (LL, "20-871-b-1-2", CODE + "20-871(b)(1)-(2)", "b. Notices required.", "3. If not disclosed",
     "Candidates and employees who live in the city must be told at least ten business days before use that an AEDT "
     "will be used and which job qualifications and characteristics it will assess, and must be allowed to request "
     "an alternative selection process or accommodation."),
    (LL, "20-871-b-3", CODE + "20-871(b)(3)", "3. If not disclosed", "§ 20-872 Penalties.",
     "If not on the website, the type and source of data the AEDT collects and the data retention policy must be "
     "given within 30 days of a written request, unless disclosure would violate law or interfere with a law "
     "enforcement investigation."),
    (LL, "20-872", CODE + "20-872", "§ 20-872 Penalties.", "§ 20-873 Enforcement.",
     "Civil penalties are up to $500 for a first violation and $500 to $1,500 for each later one. Each day of use "
     "in violation and each missed notice is a separate violation."),
    (RULE, "5-300-aedt", RCNY + "5-300 (automated employment decision tool)",
     "Automated Employment Decision Tool. “Automated", "Bias Audit. “Bias audit” means",
     "For the AEDT definition, substantially assisting or replacing discretionary decision making means relying "
     "solely on a simplified output, weighting it more than any other criterion, or using it to overrule conclusions "
     "from other factors, including human decision-making."),
    (RULE, "5-300-candidate", RCNY + "5-300 (candidate for employment)", "Candidate for Employment.",
     "Category. “Category”",
     "A candidate for employment is a person who has applied for a specific position by submitting what the employer "
     "or agency requires."),
    (RULE, "5-300-category", RCNY + "5-300 (category)", "Category. “Category”", "Code. “Code”",
     "Categories are the EEO-1 component 1 categories employers report to the EEOC."),
    (RULE, "5-300-distribution-date", RCNY + "5-300 (distribution date)", "Distribution Date.",
     "Employment Decision. “Employment decision”",
     "The distribution date is the date the employer or agency began using a specific AEDT."),
    (RULE, "5-300-independent-auditor", RCNY + "5-300 (independent auditor)", "Independent Auditor.", "Impact Ratio.",
     "An independent auditor can exercise objective, impartial judgment and has not been involved in using, "
     "developing or distributing the AEDT, and during the audit has no employment relationship or financial interest "
     "in the employer, agency or vendor."),
    (RULE, "5-300-impact-ratio", RCNY + "5-300 (impact ratio)", "Impact Ratio.", "_________selection rate",
     "The impact ratio is a category's selection rate divided by the most selected category's, or its scoring rate "
     "divided by the highest scoring category's. The rule's displayed formulas are omitted; they restate this text."),
    (RULE, "5-300-ml", RCNY + "5-300 (machine learning, statistical modeling, data analytics, or artificial intelligence)",
     "Machine learning, statistical modeling, data analytics, or artificial intelligence. “Machine", "Scoring Rate.",
     "The phrase means computer-based techniques that generate a prediction or classification and for which a "
     "computer at least in part identifies the inputs, their relative importance, or other model parameters."),
    (RULE, "5-300-scoring-rate", RCNY + "5-300 (scoring rate)", "Scoring Rate.", "Screen. “Screen”",
     "The scoring rate is the rate at which people in a category score above the sample's median AEDT score."),
    (RULE, "5-300-screen", RCNY + "5-300 (screen)", "Screen. “Screen”", "Selection Rate.",
     "To screen is to decide whether a candidate, or an employee being considered for promotion, should be selected "
     "or advanced in the hiring or promotion process."),
    (RULE, "5-300-selection-rate", RCNY + "5-300 (selection rate)", "Selection Rate.", "Example. If 100 Hispanic",
     "The selection rate is the rate at which people in a category move forward or are assigned a classification by "
     "the AEDT. The rule's worked example is omitted."),
    (RULE, "5-300-simplified-output", RCNY + "5-300 (simplified output)", "Simplified output.", "Test data.",
     "Simplified output is a prediction or classification, such as a score, tag, recommendation or ranking. Output "
     "from tools that only translate or transcribe, such as converting a resume from PDF, is not."),
    (RULE, "5-301-a", RCNY + "5-301(a)", "(a) An employer or employment agency may not use or continue",
     "(b) Where an AEDT selects",
     "An AEDT may not be used if more than a year has passed since its most recent bias audit."),
    (RULE, "5-301-b", RCNY + "5-301(b)", "(b) Where an AEDT selects", "Example: An employer wants",
     "Where the AEDT selects or classifies people, the audit must calculate selection rates and impact ratios for "
     "sex, race/ethnicity and intersectional categories, for each classification group, and report how many people "
     "were left out as unknown. The rule's example and tables are omitted."),
    (RULE, "5-301-c", RCNY + "5-301(c)", "(c) Where an AEDT scores", "(d) Notwithstanding the requirements",
     "Where the AEDT scores people, the audit must calculate the median score, scoring rates and impact ratios for "
     "sex, race/ethnicity and intersectional categories, and report how many people were left out as unknown."),
    (RULE, "5-301-d", RCNY + "5-301(d)", "(d) Notwithstanding the requirements", "Example: An employer uses an AEDT",
     "The auditor may exclude a category under 2% of the audit data from impact ratios, but the summary must justify "
     "it and still give that category's count and rate. The rule's example and tables are omitted."),
    (RULE, "5-302", RCNY + "5-302(a)-(b)", "(a) Historical Data. A bias audit", "Example 1: An employer",
     "Audits must use historical data, which may pool several employers; an employer may rely on a pooled audit only "
     "if it contributed its own data or has never used the tool. Test data is allowed when historical data is "
     "insufficient, and the summary must explain why and how it was made. The rule's examples are omitted."),
    (RULE, "5-303", RCNY + "5-303", "§ 5-303 Published Results.", "§ 5-304 Notice",
     "Before use, publish clearly on the careers website the date and summary of the latest bias audit (data source, "
     "unknown-category count, applicant counts, rates and impact ratios for all categories) and the distribution "
     "date. A clearly labeled link works. Keep it posted for six months after last use."),
    (RULE, "5-304-a-c", RCNY + "5-304(a)-(c)", "§ 5-304 Notice", "(d) To comply with § 20-871(b)(3)",
     "The notice must say how to request an alternative selection process or accommodation. Candidates can be "
     "notified on the careers website, in the job posting, or by mail or email; employees in a written policy, a "
     "posting, or by mail or email; in each case at least ten business days before use."),
    (RULE, "5-304-d", RCNY + "5-304(d)", "(d) To comply with § 20-871(b)(3)", "\x00END",
     "Post the AEDT data retention policy, the type and source of data collected, and how to request them in writing; "
     "answer written requests within 30 days; and explain any refusal based on law or an investigation."),
]


def main(ll_src, noa_src, out):
    ll = flatten(ll_src, drop=LL_DROP, carryover=True)
    noa = flatten(noa_src, drop=NOA_DROP)
    noa_body = noa[0].index("Section 1. Chapter 5 of Title 6")
    cursors = {LL: ll[0].index("§ 20-870 Definitions."), RULE: noa_body}
    docs = {LL: ll, RULE: (noa[0] + " \x00END", noa[1])}
    provisions = []
    for src, pid, cite, start, end, summary in PROVISIONS:
        flat, starts = docs[src]
        text, pages, cursors[src] = cut(flat, starts, start, end, cursors[src])
        where = "Legislation text" if src == LL else "Notice of adoption"
        page = (f"p. {pages[0]}" if len(pages) == 1 else f"pp. {pages[0]}-{pages[-1]}")
        provisions.append({"id": f"nyc-{pid}", "citation": cite, "source": src, "location": f"{where}, {page}",
                           **({"effective_from": "2023-01-01"} if src == LL else {}),
                           "text": text, "summary": summary})
    path = Path(out)
    old = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    pack = {
        "id": "us-nyc-ll144",
        "title": "New York City Local Law 144 of 2021 and DCWP rules: automated employment decision tools",
        "jurisdiction": "US-NY", "version": "0.1.0", "lifecycle": "effective", "as_of": "2026-10-26",
        "sources": [
            {"id": LL, "title": "Local Law 144 of 2021 (Int. No. 1894-A), enacted text, Admin. Code §§ 20-870 to 20-874",
             "publisher": "New York City Council", "primary": True, "retrieved_on": "2026-10-26",
             "url": "https://legistar.council.nyc.gov/LegislationDetail.aspx?ID=4344524&GUID=B051915D-A9AC-451E-81F8-6596032FA3F9"},
            {"id": RULE, "title": "Notice of Adoption of Final Rule, Use of Automated Employment Decisionmaking Tools "
                                  "(6 RCNY §§ 5-300 to 5-304)",
             "publisher": "New York City Department of Consumer and Worker Protection", "primary": True,
             "retrieved_on": "2026-10-26",
             "url": "https://rules.cityofnewyork.us/wp-content/uploads/2023/04/DCWP-NOA-for-Use-of-Automated-Employment-Decisionmaking-Tools-2.pdf"},
        ],
        "provisions": provisions,
        "facts": old.get("facts", []), "rules": old.get("rules", []),
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(pack, f, sort_keys=False, allow_unicode=True, width=110)


if __name__ == "__main__":
    main(*sys.argv[1:4])
