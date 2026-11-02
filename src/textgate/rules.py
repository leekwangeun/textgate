"""Pieces an app builds its rule file from: words, groups of words and groups of forbidden patterns.

Every model here refuses fields it does not know. A typo in a rule file then stops the program at load time,
instead of being ignored and quietly leaving a check out.
"""

import re
import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Word = Annotated[str, Field(min_length=1)]
# one of these words is enough
Group = Annotated[list[Word], Field(min_length=1)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Forbid(Strict):
    """Patterns (Python regular expressions) that may not appear anywhere.

    A match is reported as "<label>: <matched text>", or as the label alone when quote_match is false.
    """

    label: Word
    patterns: Annotated[list[re.Pattern[str]], Field(min_length=1)]
    quote_match: bool = True


class _ForbidFile(BaseModel):
    # the rest of the file belongs to the app
    model_config = ConfigDict(extra="ignore")

    forbid: Annotated[list[Forbid], Field(min_length=1)]


def load_forbid(path: str | Path) -> list[Forbid]:
    """The [[forbid]] tables of a TOML file."""
    with open(path, "rb") as f:
        return _ForbidFile.model_validate(tomllib.load(f)).forbid
