import dataclasses
import json

from textgate import Summary, recheck, sample
from textgate.sampling import failure_kind
from tests.fakes import Busy, ScriptedWriter, judge, spec


class Clock:
    """A clock the test moves by hand, so pacing is checked without waiting."""

    def __init__(self):
        self.now = 0.0
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.slept.append(round(s, 2))
        self.now += s


def run(writer, n, tmp_path, **kwargs):
    clock = Clock()
    s = sample(spec(writer, **kwargs), n, tmp_path / "out.jsonl", sleep=clock.sleep, clock=clock, log=lambda _: None)
    return s, clock, [json.loads(x) for x in (tmp_path / "out.jsonl").read_text(encoding="utf-8").splitlines()]


def test_summary_counts_drafts_items_failures_and_tokens(tmp_path):
    s, _, records = run(ScriptedWriter("좋아", Busy("429 RESOURCE_EXHAUSTED"), "괴물이야"), 3, tmp_path)
    assert (s.asked, s.written, s.usable) == (3, 2, 2)
    assert (s.items_passed, s.items_checked) == (2, 4)
    assert s.failures == {"Busy 429": 1}
    assert s.problems == {"무서운 말": 2}
    assert s.tokens == [(100, 50), (100, 50)]
    assert len(records) == 2
    assert records[1]["verdict"]["items"] == {k: ["무서운 말: 괴물"] for k in records[1]["request"]["keys"]}
    assert records[0]["tokens"] == [100, 50]


def test_calls_are_paced_by_start_time_and_wait_after_a_failure(tmp_path):
    _, clock, _ = run(ScriptedWriter(Busy("503 UNAVAILABLE"), "좋아", "좋아"), 3, tmp_path,
                      min_gap_s=15, after_failure_s=30)
    # first call at once; after the failure 30 s, so the next start is already 15 s past the last; then 15 s
    assert clock.slept == [0.0, 30.0, 0.0, 15.0]


def test_the_cost_line_uses_the_price():
    s = Summary(asked=1, tokens=[(1_000_000, 1_000_000)])
    assert any("$4.5000 a draft" in line for line in s.lines(price=(0.75, 3.75)))


def test_failure_kind_names_the_status_when_there_is_one():
    assert failure_kind(Busy("503 UNAVAILABLE. {'error': ...}")) == "Busy 503"
    assert failure_kind(TimeoutError("read timed out")) == "TimeoutError"


def test_recheck_judges_saved_drafts_again_and_reports_changes(tmp_path):
    run(ScriptedWriter("좋아", "피가 났어"), 2, tmp_path)
    saved = tmp_path / "out.jsonl"
    same, changes = recheck(spec(ScriptedWriter()), [saved])
    assert changes == [] and same.asked == 2

    def stricter(req, draft):
        v = judge(req, draft)
        first = req["keys"][0]
        if "좋아" in draft.get(first, ""):
            v.items[first] = ["새 규칙"]
        return v

    s, changes = recheck(dataclasses.replace(spec(ScriptedWriter()), judge=stricter), [saved])
    assert len(changes) == 1 and changes[0].where.endswith(":1")
    assert s.problems["새 규칙"] == 1


def test_records_without_a_verdict_are_judged_but_never_changed(tmp_path):
    old = tmp_path / "old.jsonl"
    old.write_text(json.dumps({"request": {"keys": ["A"]}, "draft": {"title": "t", "A": "괴물"}}) + "\n\n",
                   encoding="utf-8")
    s, changes = recheck(spec(ScriptedWriter()), [old])
    assert s.asked == 1 and s.items_passed == 0 and changes == []
