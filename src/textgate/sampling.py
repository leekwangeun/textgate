"""Measuring a writer: N real drafts through the app's judge, and the saved drafts again after a rule change.

A unit test can say whether the judge is right about a given sentence. Only real drafts can say how often the
model writes something the judge accepts, why calls fail, how long a draft takes and what it costs.
"""
import json
import random
import re
import statistics
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .check import Verdict

_STATUS = re.compile(r"\b([45]\d\d)\b")


@dataclass(frozen=True)
class Written:
    draft: Any
    model: str
    tokens_in: int | None = None
    # thinking counts as output where the provider bills it that way
    tokens_out: int | None = None


@dataclass(frozen=True)
class Spec:
    """What an app hands to textgate. Requests and drafts may be pydantic models, dataclasses or plain dicts."""

    make_request: Callable[[random.Random], Any]
    write: Callable[[Any], Written]
    judge: Callable[[Any, Any], Verdict]
    # rebuild a request and a draft from a saved record, for recheck
    read_request: Callable[[Any], Any]
    read_draft: Callable[[Any], Any]
    # seconds between the starts of two calls, and after a failed call (rate limits)
    min_gap_s: float = 0.0
    after_failure_s: float = 0.0
    # USD per 1M tokens in and out, to show what a run cost
    price: tuple[float, float] | None = None


def failure_kind(e: BaseException) -> str:
    """The exception name and the HTTP status in its message, e.g. "ClientError 429"."""
    m = _STATUS.search(str(e))
    return f"{type(e).__name__} {m.group(1)}" if m else type(e).__name__


def to_jsonable(x: Any) -> Any:
    if hasattr(x, "model_dump"):
        return x.model_dump(mode="json")
    if is_dataclass(x) and not isinstance(x, type):
        return asdict(x)
    return x


@dataclass
class Summary:
    asked: int = 0
    failures: Counter[str] = field(default_factory=Counter)
    usable: int = 0
    items_checked: int = 0
    items_passed: int = 0
    # problems by kind: the text before the first ":"
    problems: Counter[str] = field(default_factory=Counter)
    seconds: list[float] = field(default_factory=list)
    tokens: list[tuple[int, int]] = field(default_factory=list)

    @property
    def written(self) -> int:
        return self.asked - sum(self.failures.values())

    def add(self, v: Verdict) -> None:
        self.usable += v.usable
        self.items_checked += len(v.checked)
        self.items_passed += v.passed
        for p in v.problems():
            self.problems[p.split(":")[0]] += 1

    def lines(self, price: tuple[float, float] | None = None) -> list[str]:
        out = [f"written {self.written}/{self.asked}, usable {self.usable}/{self.written}, "
               f"items passed {self.items_passed}/{self.items_checked}"]
        if self.failures:
            out.append(f"failed calls: {dict(self.failures.most_common())}")
        if self.seconds:
            out.append(f"seconds per draft: median {statistics.median(self.seconds):.1f}, max {max(self.seconds):.1f}")
        if self.tokens:
            t_in = sum(t[0] for t in self.tokens) / len(self.tokens)
            t_out = sum(t[1] for t in self.tokens) / len(self.tokens)
            line = f"tokens per draft: in {t_in:.0f}, out {t_out:.0f}"
            if price:
                usd = (t_in * price[0] + t_out * price[1]) / 1e6
                line += f", about ${usd:.4f} a draft, ${usd * len(self.tokens):.3f} for this run"
            out.append(line)
        out.append(f"problems: {dict(self.problems.most_common())}")
        return out


def sample(spec: Spec, n: int, out: Path, seed: int = 7,
           sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
           log: Callable[[str], None] = print) -> Summary:
    """Ask for n drafts and write one JSON line per draft to out (a folder or a .jsonl file)."""
    if out.suffix != ".jsonl":
        out = out / f"sample-{datetime.now():%Y%m%d-%H%M}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    r = random.Random(seed)
    s = Summary()
    with open(out, "w", encoding="utf-8") as f:
        last_start = -spec.min_gap_s
        for i in range(n):
            req = spec.make_request(r)
            s.asked += 1
            # pace by start time: a failure comes back fast and must not shorten the gap
            sleep(max(0.0, last_start + spec.min_gap_s - clock()))
            started = last_start = clock()
            try:
                w = spec.write(req)
            except Exception as e:
                s.failures[failure_kind(e)] += 1
                log(f"{i + 1}/{n} writer failed: {e!r}"[:300])
                sleep(spec.after_failure_s)
                continue
            seconds = clock() - started
            s.seconds.append(seconds)
            tokens = None
            if w.tokens_in is not None and w.tokens_out is not None:
                tokens = (w.tokens_in, w.tokens_out)
                s.tokens.append(tokens)
            v = spec.judge(req, w.draft)
            s.add(v)
            f.write(json.dumps({"request": to_jsonable(req), "draft": to_jsonable(w.draft), "model": w.model,
                                "seconds": round(seconds, 2), "tokens": tokens, "verdict": v.to_dict()},
                               ensure_ascii=False) + "\n")
            f.flush()
            log(f"{i + 1}/{n} {seconds:.1f}s whole={'ok' if v.usable else v.whole} dropped={list(v.items)}")
    log(f"drafts: {out}")
    return s


@dataclass(frozen=True)
class Change:
    where: str
    before: dict[str, Any]
    after: dict[str, Any]


def recheck(spec: Spec, files: Iterable[Path]) -> tuple[Summary, list[Change]]:
    """Judge saved drafts again with today's rules. Records saved without a verdict count but never as changed."""
    s = Summary()
    changes = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                if not line.strip():
                    continue
                rec = json.loads(line)
                v = spec.judge(spec.read_request(rec["request"]), spec.read_draft(rec["draft"]))
                s.asked += 1
                s.add(v)
                if "verdict" in rec and rec["verdict"] != v.to_dict():
                    changes.append(Change(f"{path}:{line_no}", rec["verdict"], v.to_dict()))
    return s, changes
