"""A tiny app for the tests: a request is a list of item keys, a draft maps each key to a sentence."""

import random
from collections.abc import Callable
from typing import Any

from textgate import Forbid, Spec, Verdict, Written, find_forbidden

Request = dict[str, list[str]]
Draft = dict[str, str]

FORBID = [Forbid(label="무서운 말", patterns=["괴물", r"(?<![가-힣])피가"])]


def make_request(r: random.Random) -> Request:
    return {"keys": r.sample(["A", "B", "C"], 2)}


def judge(req: Request, draft: Draft) -> Verdict:
    v = Verdict(checked=list(req["keys"]))
    if not draft.get("title"):
        v.whole.append("title 비어 있음")
    for k in req["keys"]:
        problems = find_forbidden(draft.get(k, ""), FORBID) if k in draft else ["장면 없음"]
        if problems:
            v.items[k] = problems
    return v


class ScriptedWriter:
    """Hands out the given drafts (or raises the given exceptions) in order."""

    def __init__(self, *results: str | Exception) -> None:
        self.results = list(results)

    def __call__(self, req: Request) -> Written:
        x = self.results.pop(0)
        if isinstance(x, Exception):
            raise x
        return Written(
            draft={"title": "제목", **{k: x for k in req["keys"]}}, model="fake", tokens_in=100, tokens_out=50
        )


def spec(writer: Callable[[Request], Written], **kwargs: Any) -> Spec:
    return Spec(make_request=make_request, write=writer, judge=judge, read_request=dict, read_draft=dict, **kwargs)


class Busy(Exception):
    pass


# for the CLI test: one good draft, one call failing like a rate limit, one draft with a scary word
SPEC = spec(ScriptedWriter("좋아", Busy("429 RESOURCE_EXHAUSTED"), "괴물이야"))
