"""Checks an app combines into its own judge, and the verdict the judge returns.

A verdict has two scopes. A problem in a line the whole draft depends on (a title, a greeting) makes the draft
unusable. A problem in one item (one scene, one answer) drops only that item, and the app can fill it in from
its own reviewed text.
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from .normalize import norm
from .rules import Forbid


def find_forbidden(text: str, groups: Iterable[Forbid]) -> list[str]:
    found = []
    for group in groups:
        for p in group.patterns:
            m = p.search(text)
            if m:
                found.append(f"{group.label}: {m.group(0)}" if group.quote_match else group.label)
    return found


def too_long(name: str, text: str, limit: int) -> list[str]:
    if not text.strip():
        return [f"{name} 비어 있음"]
    return [f"{name} 길이 {len(text)} > {limit}"] if len(text) > limit else []


def missing(text: str, groups: Iterable[Sequence[str]]) -> list[list[str]]:
    """The groups none of whose words are in the text, ignoring spacing and punctuation."""
    t = norm(text)
    return [list(g) for g in groups if not any(norm(w) in t for w in g)]


def present(text: str, words: Iterable[str]) -> list[str]:
    """The words that are in the text, ignoring spacing and punctuation."""
    t = norm(text)
    return [w for w in words if norm(w) in t]


@dataclass
class Verdict:
    # problems that make the whole draft unusable
    whole: list[str] = field(default_factory=list)
    # item key -> problems; only the items that failed
    items: dict[str, list[str]] = field(default_factory=dict)
    # every item key that was checked, so the passed ones can be counted
    checked: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return not self.whole

    @property
    def clean(self) -> bool:
        return not self.whole and not self.items

    @property
    def passed(self) -> int:
        return len([k for k in self.checked if k not in self.items])

    def problems(self) -> Iterator[str]:
        yield from self.whole
        for ps in self.items.values():
            yield from ps

    def to_dict(self) -> dict[str, Any]:
        return {"whole": self.whole, "items": self.items, "checked": self.checked}
