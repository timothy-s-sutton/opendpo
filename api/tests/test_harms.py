"""The harm list (WF-25): quotes checked against verified text, sign-offs that lapse on any
change, and risks that may only name signed-off harms."""
import shutil
from datetime import date

import pytest
import yaml

from opendpo import assessment as engine
from opendpo import content, harms

from .test_triage import all_rules_usable


@pytest.fixture(scope="module")
def lib():
    return content.load()


@pytest.fixture(scope="module")
def tags(lib):
    return {t.id for t in engine.load_template(lib).framework_tags}


def copy_harms(tmp_path, edit=None, signoffs=None):
    d = tmp_path / "harms"
    shutil.copytree(harms.HARMS_DIR, d)
    if edit:
        raw = yaml.safe_load((d / "harms.yaml").read_text())
        edit(raw)
        (d / "harms.yaml").write_text(yaml.safe_dump(raw, allow_unicode=True))
    if signoffs is not None:
        (d / "verification.yaml").write_text(yaml.safe_dump(signoffs))
    return d


def sign_all(lib, tags, d):
    hs = harms.load(lib, tags, d)
    return [{"harm": s.harm.id, "fingerprint": s.harm.fingerprint, "verified_by": "Tester",
             "verified_on": date(2026, 10, 31)} for s in hs.statuses]


def test_eight_harms_from_7152_a_5(lib, tags):
    hs = harms.load(lib, tags)
    assert [s.harm.clause for s in hs.statuses] == ["(A)", "(B)", "(C)", "(D)", "(E)", "(F)", "(G)", "(H)"]
    assert all(s.harm.named_by == "ccpa-7152-a-5" for s in hs.statuses)
    # The only thing between these entries and use is the sign-off.
    for s in hs.statuses:
        assert all("signed off" in p for p in s.problems), (s.harm.id, s.problems)


def test_signed_off_harms_are_usable(lib, tags, tmp_path):
    d = copy_harms(tmp_path)
    (d / "verification.yaml").write_text(yaml.safe_dump(sign_all(lib, tags, d)))
    assert len(harms.load(lib, tags, d).usable()) == 8


def test_any_change_lapses_the_sign_off(lib, tags, tmp_path):
    d = copy_harms(tmp_path)
    signoffs = sign_all(lib, tags, d)

    def reword(raw):
        raw["harms"][1]["description"] = "Something else."
    d2 = copy_harms(tmp_path / "b", edit=reword, signoffs=signoffs)
    st = harms.load(lib, tags, d2).by_id()["harm-discrimination"]
    assert not st.usable and "changed after it was signed off" in st.problems[0]


def test_misquote_is_caught(lib, tags, tmp_path):
    def misquote(raw):
        raw["harms"][0]["quote"] = "Authorized access to personal information."
    d = copy_harms(tmp_path, edit=misquote)
    st = harms.load(lib, tags, d).by_id()["harm-security"]
    assert any("word for word" in p for p in st.problems)


def test_unverified_link_blocks_use():
    lib = content.load()
    lib.verifications["us-nyc-ll144"].pop("nyc-5-301-b")
    tags = {t.id for t in engine.load_template(lib).framework_tags}
    st = harms.load(lib, tags).by_id()["harm-discrimination"]
    assert any("nyc-5-301-b has not been verified" in p for p in st.problems)


def test_unknown_link_is_refused(lib, tags, tmp_path):
    def bad(raw):
        raw["harms"][0]["related"].append({"provision": "ccpa-9999", "why": "Not real."})
    with pytest.raises(ValueError, match="ccpa-9999"):
        harms.load(lib, tags, copy_harms(tmp_path, edit=bad))


def test_risk_may_only_name_a_signed_off_harm(lib, tags):
    tpl = engine.load_template(lib)
    r = {"id": "r1", "title": "Qualified applicants screened out", "source_and_cause": "Model trained on past hires",
         "likelihood": "high", "severity": "high", "harm": "harm-discrimination"}
    with pytest.raises(engine.Rejected, match="signed-off harm list"):
        engine.parse(tpl.section("risks"), {"risks": [r]}, tags, set())
    assert engine.parse(tpl.section("risks"), {"risks": [r]}, tags, {"harm-discrimination"})["risks"][0]["harm"] \
        == "harm-discrimination"


def test_worksheet_has_a_box_per_harm(lib, tags):
    text = harms.worksheet(all_rules_usable(), harms.load(lib, tags))
    assert text.count("- [ ] Entry is accurate") == 8
    assert "Cal. Code Regs. tit. 11, § 7152(a)(5)(B)" in text
