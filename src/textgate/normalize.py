import re

_PUNCT = re.compile(r"[\s.,!?~…·'\"“”‘’()\-]")


def norm(text: str) -> str:
    """Spacing and punctuation vary between drafts ("하나, 둘, 셋!" / "하나 둘 셋"), the words do not."""
    return _PUNCT.sub("", text)
