import pytest
from pydantic import ValidationError

from textgate import Forbid, Verdict, find_forbidden, load_forbid, missing, norm, present, too_long


def test_norm_drops_spacing_and_punctuation_only():
    assert norm("하나, 둘, 셋!") == norm("하나 둘 셋") == "하나둘셋"
    assert norm("(왼쪽)") == "왼쪽"


def test_forbidden_quotes_the_match_unless_told_not_to():
    groups = [Forbid(label="무서운 말", patterns=["괴물", "귀신"]),
              Forbid(label="영어", patterns=["[A-Za-z]"], quote_match=False)]
    assert find_forbidden("괴물과 귀신 OK", groups) == ["무서운 말: 괴물", "무서운 말: 귀신", "영어"]
    assert find_forbidden("평범한 문장", groups) == []


def test_a_broken_pattern_or_an_unknown_field_is_refused():
    with pytest.raises(ValidationError):
        Forbid(label="x", patterns=["피(가"])
    with pytest.raises(ValidationError):
        Forbid(label="x", patterns=["a"], quote=False)
    with pytest.raises(ValidationError):
        Forbid(label="x", patterns=[])


def test_load_forbid_reads_only_the_forbid_tables(tmp_path):
    f = tmp_path / "rules.toml"
    f.write_text("[limits]\ntitle = 20\n\n[[forbid]]\nlabel = \"무서운 말\"\npatterns = ['괴물']\n", encoding="utf-8")
    [group] = load_forbid(f)
    assert group.label == "무서운 말"
    assert group.patterns[0].pattern == "괴물"


def test_too_long_and_empty():
    assert too_long("title", "짧은 제목", 20) == []
    assert too_long("title", "가" * 21, 20) == ["title 길이 21 > 20"]
    assert too_long("title", "  ", 20) == ["title 비어 있음"]


def test_missing_and_present_ignore_spacing():
    groups = [["펭귄"], ["왼쪽", "좌측"], ["하나둘셋"]]
    assert missing("펭귄은 좌측 방! 하나, 둘, 셋!", groups) == []
    assert missing("펭귄은 오른쪽 방", groups) == [["왼쪽", "좌측"], ["하나둘셋"]]
    assert present("오른 쪽으로 가", ["오른쪽", "위쪽"]) == ["오른쪽"]


def test_verdict_scopes():
    v = Verdict(checked=["A", "B", "C"])
    assert v.usable and v.clean and v.passed == 3
    v.items["B"] = ["장면 없음"]
    assert v.usable and not v.clean and v.passed == 2
    v.whole.append("title 비어 있음")
    assert not v.usable
    assert list(v.problems()) == ["title 비어 있음", "장면 없음"]
