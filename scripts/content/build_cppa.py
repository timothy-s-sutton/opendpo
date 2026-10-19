"""Draft the CPPA content pack from the approved regulation text.

    pdftotext -layout ccpa_updates_cyber_risk_admt_appr_text.pdf cppa.txt
    python build_cppa.py cppa.txt ../../content/packs/us-ca-cppa-admt-ra/pack.yaml

Every provision's text is copied from the source, never retyped. The rules are
OpenDPO's reading of those provisions and must be verified (CNT-01).
"""
import sys

import yaml

from extract import between, clean_lines

SRC = "cppa-regs-2026"
T11 = "Cal. Code Regs. tit. 11, § "

# id, citation, start marker, end marker, OpenDPO summary
PROVISIONS = [
    ("7001-e", "7001(e)", "(e)   “Automated decisionmaking technology” or “ADMT”", "(1)   For purposes of this definition, to “substantially",
     "ADMT is technology that processes personal information and uses computation to replace, or substantially replace, human decisionmaking."),
    ("7001-e-1", "7001(e)(1)", "(1)   For purposes of this definition, to “substantially", "(2)   ADMT includes profiling",
     "Substantially replacing human decisionmaking means using the output without human involvement. Human involvement needs a reviewer who knows how to use the output, reviews it with other relevant information, and has authority to make or change the decision."),
    ("7001-e-2-3", "7001(e)(2)-(3)", "(2)   ADMT includes profiling", "(f)   (e) “Categories of sources”",
     "ADMT includes profiling that replaces or substantially replaces human decisionmaking; routine IT tools are excluded unless they replace human decisionmaking. Not cited by any rule: shown as on-screen guidance for the intake question on the AI's role, so excluded tools are answered None and an analyst confirms."),
    ("7001-aaa", "7001(aaa)", "(aaa) “Sensitive location”", "(bbb) “Sensitive personal information”",
     "Lists the physical places that count as sensitive locations, such as healthcare facilities, shelters, schools, union offices and places of worship."),
    ("7001-ddd", "7001(ddd)", "(ddd) “Significant decision” means", "(eee) “Systematic observation”",
     "A significant decision provides or denies financial or lending services, housing, education, employment or contracting opportunities or compensation, or healthcare services. Hiring is an employment decision. Advertising is not a significant decision."),
    ("7001-eee", "7001(eee)", "(eee) “Systematic observation”", "(fff) “Train” for the purposes",
     "Systematic observation is methodical and regular or continuous observation, including video or audio recording and biometric identification technologies."),
    ("7150-a", "7150(a)", "(a)   Every business whose processing of consumers’ personal information presents", "(b)   Each of the following processing activities presents significant risk",
     "A business must conduct a risk assessment before starting processing that presents significant risk to consumers' privacy."),
    ("7150-b-1", "7150(b)(1)", "(b)   Each of the following processing activities presents significant risk", "(2)   Processing sensitive personal information.",
     "Selling or sharing personal information presents significant risk."),
    ("7150-b-2", "7150(b)(2)", "(2)   Processing sensitive personal information.", "(3)   Using ADMT for a significant decision concerning a consumer.",
     "Processing sensitive personal information presents significant risk, except an employer's processing of workforce sensitive data solely for listed HR administration purposes."),
    ("7150-b-3", "7150(b)(3)", "(3)   Using ADMT for a significant decision concerning a consumer.", "(4)   Using automated processing to infer",
     "Using ADMT for a significant decision concerning a consumer presents significant risk."),
    ("7150-b-4", "7150(b)(4)", "(4)   Using automated processing to infer", "(5)   Using automated processing to infer",
     "Automated inference about applicants, students, employees or contractors based on systematic observation presents significant risk."),
    ("7150-b-5", "7150(b)(5)", "(5)   Using automated processing to infer", "(6)   Processing the personal information of consumers, which the business",
     "Automated inference based on a consumer's presence in a sensitive location presents significant risk, except solely to deliver goods or provide transportation there."),
    ("7150-b-6", "7150(b)(6)", "(6)   Processing the personal information of consumers, which the business", "(c)   Illustrative examples of when a business must conduct a risk assessment",
     "Processing personal information the business intends to use to train ADMT for a significant decision, or to train identity, facial-recognition, emotion-recognition or biometric profiling technology, presents significant risk."),
    ("7152-a", "7152(a)", "(a)   A business must conduct a risk assessment to determine whether the risks", "(1)   Identify and document in a risk assessment report the business’s purpose",
     "A risk assessment weighs the risks to consumers' privacy against the benefits to the consumer, the business, other stakeholders and the public."),
    ("7152-a-1", "7152(a)(1)", "(1)   Identify and document in a risk assessment report the business’s purpose", "(2)   Identify and document in a risk assessment report the categories",
     "Document a specific, non-generic purpose for the processing."),
    ("7152-a-2", "7152(a)(2)", "(2)   Identify and document in a risk assessment report the categories", "(3)   Identify and document in a risk assessment report the following",
     "Document the categories of personal information, including sensitive personal information, and the minimum necessary for the purpose."),
    ("7152-a-3", "7152(a)(3)", "(3)   Identify and document in a risk assessment report the following", "(4)   Identify the benefits to the business",
     "Document the operational elements: collection and sources, retention, how the business interacts with consumers, approximate number of consumers, disclosures, recipients, and for ADMT, its logic and how its output is used."),
    ("7152-a-4", "7152(a)(4)", "(4)   Identify the benefits to the business", "(5)   Identify the negative impacts to consumers’ privacy",
     "Identify specific, non-generic benefits to the business, consumers, other stakeholders and the public."),
    ("7152-a-5", "7152(a)(5)", "(5)   Identify the negative impacts to consumers’ privacy", "(6)   Identify and document in a risk assessment report any safeguards",
     "Identify negative impacts to consumers' privacy and their sources and causes; lists examples from security incidents to discrimination, economic, physical, reputational and psychological harms."),
    ("7152-a-6", "7152(a)(6)", "(6)   Identify and document in a risk assessment report any safeguards", "(7)   Identify and document in a risk assessment report whether it will initiate",
     "Document planned safeguards, such as security controls, privacy-enhancing technologies, outside expertise, and policies ensuring ADMT works and does not discriminate."),
    ("7152-a-7-9", "7152(a)(7)-(9)", "(7)   Identify and document in a risk assessment report whether it will initiate", "Note: Authority cited",
     "Document whether the business will initiate the processing, who provided information, and the review and approval date and approvers; an approver must have authority to decide whether the processing goes ahead."),
    ("7155-a", "7155(a)", "(a)   A business must comply with the following timing requirements", "(b)   For any processing activity identified in section 7150, subsection (b), that the",
     "Assess before initiating; review at least every three years; update within 45 calendar days of a material change."),
    ("7155-b-c", "7155(b)-(c)", "(b)   For any processing activity identified in section 7150, subsection (b), that the", "Note: Authority cited",
     "Processing begun before the regulations took effect must be assessed by December 31, 2027. Keep every version while processing continues or five years after completion, whichever is later. Note: the approved text still shows OAL's placeholder for the effective date, which the Notice of Approval sets as January 1, 2026."),
    ("7200", "7200", "(a)   A business that uses ADMT to make a significant decision concerning a", "Note: Authority cited",
     "A business using ADMT for a significant decision must comply with Article 11, by January 1, 2027 for existing uses."),
    ("7220-a", "7220(a)", "(a)   A business that uses ADMT as set forth in section 7200, subsection (a), must", "(b)   The Pre-use Notice must:",
     "Give consumers a Pre-use Notice about the ADMT use and their rights to opt out and to access."),
    ("7221-a", "7221(a)", "(a)   A business must provide consumers with the ability to opt-out of the use of", "(b)   A business is not required to provide consumers with the ability to opt-out of a",
     "Provide the ability to opt out of ADMT for significant decisions, unless an exception applies."),
    ("7221-b-1", "7221(b)(1)", "(b)   A business is not required to provide consumers with the ability to opt-out of a", "(2)   For admission, acceptance, or hiring decisions as set forth",
     "No opt-out is needed if the consumer can appeal to a qualified human reviewer with authority to overturn the decision."),
    ("7221-b-2", "7221(b)(2)", "(2)   For admission, acceptance, or hiring decisions as set forth", "(3)   For allocation/assignment of work and compensation decisions as set",
     "For hiring and admission decisions, no opt-out is needed if the ADMT is used solely to assess ability to perform and works for its purpose without unlawful discrimination."),
    ("7222-a", "7222(a)", "(a)   A business that uses ADMT to make a significant decision must provide a", "(b)   When responding to a consumer’s request to access ADMT, a business must",
     "Respond to consumers' requests to access information about the business's use of ADMT."),
]


def main(src, out):
    lines = clean_lines(src)
    provisions = []
    for pid, cite, start, end, summary in PROVISIONS:
        section = "§ " + cite.split("(")[0].split("-")[0] + "."
        text, pages = between(lines, start, end, after=section)
        provisions.append({
            "id": f"cppa-{pid}", "citation": T11 + cite, "source": SRC,
            "location": f"Approved text, p. {pages[0]}" + (f"-{pages[-1]}" if len(pages) > 1 else ""),
            "effective_from": "2027-01-01" if pid.startswith(("7200", "722")) else "2026-01-01",
            "text": text, "summary": summary})
    pack = yaml.safe_load(open(out, encoding="utf-8"))
    pack["provisions"] = provisions
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump(pack, f, sort_keys=False, allow_unicode=True, width=100)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
