from datetime import date
from pathlib import Path

import pytest
import yaml

from opendpo import content

PACK = {
    "id": "test-pack", "title": "Test pack", "jurisdiction": "US-CA", "version": "0.1.0",
    "lifecycle": "effective", "as_of": "2026-10-19",
    "sources": [
        {"id": "reg", "title": "Regulation", "publisher": "Agency", "url": "https://example.gov/reg.pdf",
         "primary": True, "retrieved_on": "2026-10-19"},
        {"id": "blog", "title": "Law firm summary", "publisher": "Firm", "url": "https://example.com",
         "primary": False, "retrieved_on": "2026-10-19"},
    ],
    "provisions": [
        {"id": "p1", "citation": "Reg. § 1(a)", "source": "reg", "text": "A business shall assess.",
         "summary": "Assess."},
        {"id": "p2", "citation": "Summary", "source": "blog", "text": "Firms say assess.", "summary": "x"},
    ],
    "facts": [
        {"id": "ccpa.applies", "question": "Does the CCPA apply?", "type": "boolean"},
        {"id": "x", "question": "X?", "type": "boolean"},
    ],
    "rules": [
        {"id": "R1", "kind": "trigger", "title": "Assess", "provisions": ["p1"],
         "when": {"fact": "ccpa.applies", "equals": True}, "result": {"assessment": "a"},
         "explanation": "Because the law applies."},
        {"id": "R2", "kind": "trigger", "title": "From a blog", "provisions": ["p2"],
         "when": {"fact": "x", "equals": True}, "result": {"assessment": "b"}, "explanation": "x"},
    ],
}


def write(tmp: Path, pack: dict, records: list[dict]) -> Path:
    d = tmp / pack["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "pack.yaml").write_text(yaml.safe_dump(pack))
    (d / "verification.yaml").write_text(yaml.safe_dump(records))
    return tmp


def record(text: str) -> dict:
    return {"provision": "p1", "fingerprint": content.text_fingerprint(text),
            "verified_by": "Tim Sutton", "verified_on": "2026-10-20"}


def rule_record(pack: dict, rule_id: str = "R1") -> dict:
    rule = content.Rule.model_validate(next(r for r in pack["rules"] if r["id"] == rule_id))
    return {"rule": rule_id, "fingerprint": rule.fingerprint,
            "verified_by": "Tim Sutton", "verified_on": "2026-10-20"}


def test_unverified_rule_is_not_usable(tmp_path):
    lib = content.load(write(tmp_path, PACK, []))
    r1 = next(s for s in lib.statuses if s.rule.id == "R1")
    assert not r1.usable and "has not been verified" in r1.problems[0]
    assert lib.opa_data() == {"rules": []}


def test_verified_rule_reaches_the_engine(tmp_path):
    lib = content.load(write(tmp_path, PACK, [record("A business shall assess."), rule_record(PACK)]))
    assert [r["id"] for r in lib.opa_data()["rules"]] == ["R1"]


def test_verified_text_alone_is_not_enough(tmp_path):
    lib = content.load(write(tmp_path, PACK, [record("A business shall assess.")]))
    r1 = next(s for s in lib.statuses if s.rule.id == "R1")
    assert not r1.usable and "reading of the law has not been verified" in r1.problems[0]


def test_logic_change_lapses_rule_verification(tmp_path):
    signed = rule_record(PACK)
    changed = {**PACK, "rules": [{**PACK["rules"][0], "when": {"fact": "ccpa.applies", "equals": False}},
                                 PACK["rules"][1]]}
    lib = content.load(write(tmp_path, changed, [record("A business shall assess."), signed]))
    r1 = next(s for s in lib.statuses if s.rule.id == "R1")
    assert not r1.usable and "logic changed after it was verified" in r1.problems[0]


def test_whitespace_changes_do_not_lapse_verification(tmp_path):
    lib = content.load(write(tmp_path, PACK, [record("A business\n  shall assess."), rule_record(PACK)]))
    assert next(s for s in lib.statuses if s.rule.id == "R1").usable


def test_text_change_lapses_verification(tmp_path):
    changed = {**PACK, "provisions": [{**PACK["provisions"][0], "text": "A business may assess."},
                                      PACK["provisions"][1]]}
    lib = content.load(write(tmp_path, changed, [record("A business shall assess.")]))
    r1 = next(s for s in lib.statuses if s.rule.id == "R1")
    assert not r1.usable and "changed after it was verified" in r1.problems[0]


def test_secondary_source_can_never_be_the_citation(tmp_path):
    rec = {**record("Firms say assess."), "provision": "p2"}
    lib = content.load(write(tmp_path, PACK, [rec]))
    r2 = next(s for s in lib.statuses if s.rule.id == "R2")
    assert not r2.usable and "secondary source" in r2.problems[0]


def test_rule_citing_unknown_provision_is_rejected(tmp_path):
    bad = {**PACK, "rules": [{**PACK["rules"][0], "provisions": ["nope"]}]}
    with pytest.raises(ValueError, match="unknown provisions"):
        content.load(write(tmp_path, bad, []))


def test_conditions_are_shallow(tmp_path):
    deep = {"all": [{"any": [{"all": [{"fact": "a", "equals": 1}]}]}]}
    bad = {**PACK, "rules": [{**PACK["rules"][0], "when": deep}]}
    with pytest.raises(ValueError, match="nest at most"):
        content.load(write(tmp_path, bad, []))


def test_versions_recorded(tmp_path):
    assert content.load(write(tmp_path, PACK, [])).versions() == {"test-pack": "0.1.0"}


def test_rule_cannot_test_an_undeclared_fact(tmp_path):
    bad = {**PACK, "rules": [{**PACK["rules"][0], "when": {"fact": "nope", "equals": True}}]}
    with pytest.raises(ValueError, match="undeclared fact"):
        content.load(write(tmp_path, bad, []))


def test_rule_answer_must_be_a_valid_option(tmp_path):
    facts = PACK["facts"] + [{"id": "role", "question": "Role?", "type": "choice",
                              "options": [{"value": "a", "label": "A"}]}]
    bad = {**PACK, "facts": facts, "rules": [{**PACK["rules"][0], "when": {"fact": "role", "equals": "b"}}]}
    with pytest.raises(ValueError, match="not an answer"):
        content.load(write(tmp_path, bad, []))


def test_definitions_behind_facts_are_cited_and_must_be_verified(tmp_path):
    provisions = PACK["provisions"] + [{"id": "def", "citation": "Reg. § 0(a)", "source": "reg",
                                        "text": "Applies means applies.", "summary": "Definition."}]
    facts = [{**PACK["facts"][0], "defined_by": ["def"]}, PACK["facts"][1]]
    pack = {**PACK, "provisions": provisions, "facts": facts}
    lib = content.load(write(tmp_path, pack, [record("A business shall assess."), rule_record(pack)]))
    r1 = next(s for s in lib.statuses if s.rule.id == "R1")
    assert lib.packs[0].citations(r1.rule) == ["p1", "def"]
    assert not r1.usable and "def has not been verified" in r1.problems[0]
