from pathlib import Path

import pytest

from textgate.cli import main


@pytest.fixture
def rules(tmp_path: Path) -> Path:
    f = tmp_path / "rules.toml"
    f.write_text("[[forbid]]\nlabel = \"무서운 말\"\npatterns = ['(?<![가-힣])피가']\n", encoding="utf-8")
    return f


def test_try_shows_hits_and_fails_when_something_is_forbidden(rules: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["try", str(rules), "커피가 따뜻해"]) == 0
    assert main(["try", str(rules), "피가 났어", "괜찮아"]) == 1
    out = capsys.readouterr().out
    assert "커피가 따뜻해: ok" in out
    assert "피가 났어: 무서운 말: 피가" in out


def test_sample_then_recheck_through_the_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "run.jsonl"
    assert main(["sample", "tests.fakes:SPEC", "-n", "3", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "written 2/3, usable 2/2, items passed 2/4" in printed
    assert "failed calls: {'Busy 429': 1}" in printed

    assert main(["recheck", "tests.fakes:SPEC", str(tmp_path / "*.jsonl")]) == 0
    assert "verdict changed: 0" in capsys.readouterr().out


def test_a_spec_that_is_not_a_spec_is_refused() -> None:
    with pytest.raises(SystemExit, match=r"not a textgate\.Spec"):
        main(["recheck", "tests.fakes:FORBID", "x.jsonl"])
    with pytest.raises(SystemExit, match="module:name"):
        main(["recheck", "tests.fakes", "x.jsonl"])
