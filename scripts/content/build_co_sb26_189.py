"""Draft the Colorado SB 26-189 pack (C.R.S. 6-1-1701 to 6-1-1709, automated decision-making technology).

    pdftotext -layout 2026a_189_signed-act.pdf co_sb26_189.txt
    python build_co_sb26_189.py co_sb26_189.txt ../../content/packs/us-co-sb26-189/pack.yaml

The source of record is the signed act (approved May 14, 2026) from the Colorado General
Assembly. That PDF is a scan; its text layer was produced by OCR. Text is copied from the
text layer, never retyped. Where OCR split or merged words or misread a paragraph number,
the builder applies one of the corrections listed in OCR_FIXES, each checked by eye against
the page image, and records the corrections it applied to each provision in
ocr-corrections.yaml next to the pack so the verification worksheet can show them.

Capital letters are kept as printed: in the act they mark new statutory text.
Facts and rules are authored by hand in pack.yaml and are kept when this script reruns.
Section 6-1-1702 (developer duties) is left out of the preview, which models deployers only.
"""
import re
import sys
from pathlib import Path

import yaml

from extract import correct, cut, flatten

SRC = "co-sb26-189-signed"
CRS = "C.R.S. § "

DROP = re.compile(r"^(PAGE [0-9I ]+-SENA ?TE BILL 26-189|Capital letters or bold|through words or numbers"
                  r"|the act\.$|1\s+11\s+11$)")

# (as scanned, as printed). Paragraph numbers are corrected only with enough context to be unique.
OCR_FIXES = [
    ("OTHER WISE", "OTHERWISE"),
    ("FA VO RAB LE", "FAVORABLE"),
    ("GENERA TED", "GENERATED"),
    ("GENERA TE ", "GENERATE "),
    ("DOMAIN;OR", "DOMAIN; OR"),
    ("COMP EN SATION", "COMPENSATION"),
    ("FORA COVERED", "FOR A COVERED"),
    ("(11) ADVERTISING", "(II) ADVERTISING"),
    ("(111) SPREADSHEETS", "(III) SPREADSHEETS"),
    ("ORAN EMPLOYMENTOPPORTUNITYTHATCREATES", "OR AN EMPLOYMENT OPPORTUNITY THAT CREATES"),
    ("(C) THE LEASE", "(c) THE LEASE"),
    ("(t) HEALTH-CARE", "(f) HEALTH-CARE"),
    ("(11) DEVELOPS A COMPONENT", "(II) DEVELOPS A COMPONENT"),
    ("(Ill) HAS DESIGNED", "(III) HAS DESIGNED"),
    ("ADVERTISED,CONFIGURED,ORCONTRACTEDACOMPONENTTHATISUSEDAS",
     "ADVERTISED, CONFIGURED, OR CONTRACTED A COMPONENT THAT IS USED AS"),
    ("( 15)", "(15)"),
    ("(8) MATERIAL LIMITATIONS", "(B) MATERIAL LIMITATIONS"),
    ("DEPLOYERAND", "DEPLOYER AND"),
    ("DAT A,", "DATA,"),
    ("CONTA IN ING", "CONTAINING"),
    ("INFORMATIONREQUIREDBYSUBSECTION(2)(a)OFTHISSECTIONTOCOMPLY",
     "INFORMATION REQUIRED BY SUBSECTION (2)(a) OF THIS SECTION TO COMPLY"),
    ("SUBSECTIONS ( 1)", "SUBSECTIONS (1)"),
    ("( 4) A DEVELOPER", "(4) A DEVELOPER"),
    ("A WARE", "AWARE"),
    ("( 1) PRIOR", "(1) PRIOR"),
    ("ADMTTO", "ADMT TO"),
    ("SUBSECTION ( 1)", "SUBSECTION (1)"),
    ("RES ULTING", "RESULTING"),
    ("(l)(a)", "(1)(a)"),
    ("(2)( o)", "(2)(o)"),
    ("ORA COVERED ENTITY'S", "OR A COVERED ENTITY'S"),
    ("AS SOCIA TES", "ASSOCIATES"),
    ("160 .103", "160.103"),
    ("SPAM-AND ROBO-CALL", "SPAM- AND ROBO-CALL"),
    ("6-1-1705 (3 )", "6-1-1705 (3)"),
    ("(3 )( e)", "(3)(e)"),
]

# id, citation, start marker, end marker (as scanned), OpenDPO summary
PROVISIONS = [
    ("6-1-1701-1", "6-1-1701(1)", '(1) "ADVERSE OUTCOME" MEANS:', '(2) (a) "AUTOMATED',
     "An adverse outcome is a decision that denies, terminates, revokes or materially reduces or restricts a "
     "consumer's access to, eligibility for, selection for, compensation for or provision of an opportunity or "
     "service, or that gives materially less favorable price, compensation or other terms than similarly situated "
     "consumers receive, in a way reasonably likely to limit, delay, deny or fundamentally alter that access."),
    ("6-1-1701-2-a", "6-1-1701(2)(a)", '(2) (a) "AUTOMATED', '(b) "AUTOMATED',
     "ADMT is technology that processes personal data and uses computation to generate output, such as predictions, "
     "recommendations, classifications, rankings or scores, used to make, guide or assist a decision, judgment or "
     "determination about an individual."),
    ("6-1-1701-2-b", "6-1-1701(2)(b)", '(b) "AUTOMATED', '(3) (a) "CONSEQUENTIAL DECISION" MEANS:',
     "ADMT excludes listed routine technologies (security tools, calculators, databases, storage, networking, "
     "hosting, spell-checking, spam filtering, and spreadsheets that need human analysis and use no machine "
     "learning, foundation models or large language models), tools an individual uses solely to summarize, "
     "organize, translate, draft, route or present information for human review of administrative processing, and "
     "consumer chatbots that are not intended for consequential decisions and are under a use policy prohibiting it."),
    ("6-1-1701-3-a", "6-1-1701(3)(a)", '(3) (a) "CONSEQUENTIAL DECISION" MEANS:', '(b) "CONSEQUENTIAL DECISION" DOES NOT',
     "A consequential decision is a decision, determination or action about a consumer that relates to the "
     "provision of, or the consumer's access to, eligibility for, selection for or compensation for, a covered "
     "domain, or to differentiated price or terms reasonably likely to materially limit, delay, deny or "
     "fundamentally alter access to one."),
    ("6-1-1701-3-b", "6-1-1701(3)(b)", '(b) "CONSEQUENTIAL DECISION" DOES NOT', '(4) (a) "CONSUMER"',
     "Excluded from consequential decisions: low-stakes or routine processes that do not materially influence "
     "access (scheduling, routing, triage, communicating decisions, workflow); advertising, marketing, product "
     "recommendations, search and content moderation; manual spreadsheets; summarizing or presenting information "
     "for human review with no score, ranking, recommendation, classification, prediction or other inference that "
     "materially influences the outcome; narrow procedural tasks; cybersecurity, fraud prevention, anti-money "
     "laundering and sanctions compliance; and routine academic administration."),
    ("6-1-1701-4", "6-1-1701(4)", '(4) (a) "CONSUMER"', '(5) "COVERED ADMT"',
     "A consumer has the Colorado Privacy Act meaning and also includes an employee, a job applicant who is a "
     "Colorado resident, and anyone whose access to, eligibility for or opportunity in Colorado is evaluated in a "
     "consequential decision by a person doing business in Colorado."),
    ("6-1-1701-5", "6-1-1701(5)", '(5) "COVERED ADMT"', '(6) "COVERED DOMAIN"',
     "Covered ADMT is ADMT used to materially influence a consequential decision."),
    ("6-1-1701-6", "6-1-1701(6)", '(6) "COVERED DOMAIN"', '(7) "DEPLOYER"',
     "The covered domains are education, employment, residential real estate in Colorado, financial or lending "
     "services, insurance, health-care services, and essential government services and public benefits."),
    ("6-1-1701-7", "6-1-1701(7)", '(7) "DEPLOYER"', '(8) (a) "DEVELOPER"',
     "A deployer is a person doing business in Colorado that deploys a covered ADMT."),
    ("6-1-1701-8", "6-1-1701(8)", '(8) (a) "DEVELOPER"', '(9) "EMPLOYEE"',
     "A developer is a person doing business in Colorado that makes a covered ADMT commercially available, builds a "
     "component designed or contracted for one, or intentionally and substantially modifies an ADMT so it becomes "
     "covered. Research-only and internal-only development, a preceding developer whose system an unaffiliated "
     "person repurposes, and component makers without actual knowledge of the integration are excluded."),
    ("6-1-1701-13", "6-1-1701(13)", '(13) (a) "MATERIALLY INFLUENCE"', '(14) (a) "MATERIAL UPDATE"',
     "ADMT output materially influences a decision when it is a non-de minimis factor in making it and it affects "
     "the outcome, including by constraining, ranking, scoring, recommending or classifying. Incidental, trivial "
     "and clerical uses do not count."),
    ("6-1-1701-15", "6-1-1701(15)", '( 15) "MEANINGFUL HUMAN REVIEW"', '(16) "PERSONAL DATA"',
     "Meaningful human review is by an individual the deployer designates with authority to approve, modify or "
     "override the decision, who considers the relevant primary evidence, is trained, does not default to the "
     "system output, and can understand the output's intended use, limitations, inputs and principal factors."),
    ("6-1-1703", "6-1-1703", "A DEPLOYER SHALL RETAIN", "6-1-1704. Deployer disclosures",
     "A deployer must keep records showing compliance for at least three years after each consequential decision, "
     "or longer if other law requires, such as version identifiers, changelogs and records of mitigation changes."),
    ("6-1-1704-1-2", "6-1-1704(1)-(2)", "( 1) PRIOR TO A DEPLOYER", "(3) IF A DEPLOYER USES",
     "Before using covered ADMT to materially influence a consequential decision, a deployer must give consumers a "
     "clear and conspicuous notice and tell them how to get more information. A prominent public notice at or "
     "linked near the point of interaction satisfies this."),
    ("6-1-1704-3", "6-1-1704(3)", "(3) IF A DEPLOYER USES", "(4) (a) THE GENERAL ASSEMBLY",
     "Within 30 days after a consequential decision with an adverse outcome, the deployer must give a plain-language "
     "description of the decision and the ADMT's role, a simple way to request more about the ADMT and the personal "
     "data used, and an explanation of the consumer's rights and how to use them."),
    ("6-1-1704-8", "6-1-1704(8)", "(8) A DEPLOYER OR DEVELOPER SHALL PROVIDE", "(9) (a) FOR A CONSEQUENTIAL DECISION",
     "Notices and disclosures must be reasonably accessible to consumers with disabilities and with limited "
     "English proficiency."),
    ("6-1-1705-1", "6-1-1705(1)", "(1) (a) WHEN A CONSUMER EXPERIENCES", "(2) (a) FOR A CONSEQUENTIAL DECISION",
     "After an adverse outcome, a consumer may ask for instructions to get and correct inaccurate personal data used "
     "in the decision, and for meaningful human review and reconsideration to the extent commercially reasonable. "
     "Opinions, predictions, scores and protected evaluations need not be corrected."),
    ("6-1-1708-1-2", "6-1-1708(1)-(2)", "(1) (a) AN INSURER", "(3) (a) SECTIONS 6-1-1701",
     "Insurers and affiliates subject to section 10-3-1104.9 comply with part 17 in the practice of insurance; other "
     "insurers must still give the post-adverse outcome disclosures. Insurers' own employment decisions stay covered."),
    ("6-1-1708-3-a-b", "6-1-1708(3)(a)-(b)", "(3) (a) SECTIONS 6-1-1701", "(c) A COVERED ENTITY SHALL PROVIDE",
     "Sections 6-1-1701 to 6-1-1706 do not apply to HIPAA covered entities doing business in Colorado or their "
     "business associates, except for employment decisions. A health-care provider is exempt only if it operates "
     "from a location in Colorado. Paragraphs (c) and (d), which still apply, are not in this pack."),
    ("sb26-189-s5", "SB 26-189, § 5", "SECTION 5. Effective date", "SECTION 6. Safety clause.",
     "The act takes effect January 1, 2027, and applies to consequential decisions made on or after that date. "
     "The rulemaking deadlines and appropriation took effect on passage."),
]


def main(src, out):
    flat, starts = flatten(src, drop=DROP)
    provisions, corrections = [], {}
    cursor = flat.index("6-1-1701. Definitions.")   # past the title page
    for pid, cite, start, end, summary in PROVISIONS:
        text, pages, cursor = cut(flat, starts, start, end, cursor)
        text, applied = correct(text, OCR_FIXES)
        pid = f"co-{pid}"
        if applied:
            corrections[pid] = applied
        page = (f"p. {pages[0]}" if len(pages) == 1 else f"pp. {pages[0]}-{pages[-1]}")
        provisions.append({
            "id": pid, "citation": (CRS if cite[0].isdigit() else "Colo. ") + cite, "source": SRC,
            "location": f"Signed act, {page}",
            "effective_from": "2026-05-14" if pid == "co-sb26-189-s5" else "2027-01-01",
            "text": text, "summary": summary})
    path = Path(out)
    old = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    pack = {
        "id": "us-co-sb26-189",
        "title": "Colorado SB 26-189: automated decision-making technology in consequential decisions (C.R.S. 6-1-1701 to 6-1-1709)",
        "jurisdiction": "US-CO", "version": "0.1.0", "lifecycle": "enacted", "as_of": "2026-10-26",
        "sources": [{"id": SRC, "title": "Senate Bill 26-189, signed act (approved May 14, 2026)",
                     "publisher": "Colorado General Assembly", "primary": True, "retrieved_on": "2026-10-26",
                     "url": "https://leg.colorado.gov/bill_files/116489/download"}],
        "provisions": provisions,
        "facts": old.get("facts", []), "rules": old.get("rules", []),
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(pack, f, sort_keys=False, allow_unicode=True, width=110)
    with open(path.parent / "ocr-corrections.yaml", "w", encoding="utf-8") as f:
        f.write("# OCR corrections the builder applied, per provision: (as scanned, as printed).\n"
                "# Generated by scripts/content/build_co_sb26_189.py. Check each against the page image.\n")
        yaml.safe_dump(corrections, f, sort_keys=False, allow_unicode=True, width=110)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
