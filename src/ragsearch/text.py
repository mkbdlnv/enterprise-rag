"""Tokenisation shared by indexing and querying.

Both sides must split text the same way, otherwise BM25 never matches. The
stemmer is deliberately tiny: it folds plural and verb forms ("policies" ->
"policy", "requested" -> "request") which is most of what matters for
short enterprise queries, and costs no dependency.
"""

import re

_WORD = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)

STOPWORDS = frozenset(
    """a an and any are as at be by can do does for from get have how i if in is it its many
    me much my of on or our per should the their there this to was we what when where which
    who why will with you your""".split()
)


def stem(token: str) -> str:
    if len(token) <= 3:
        return token
    if token.endswith("ies"):
        return token[:-3] + "y"
    for suffix in ("ing", "ed"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    if token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    return [stem(w) for w in (m.lower() for m in _WORD.findall(text)) if w not in STOPWORDS]
