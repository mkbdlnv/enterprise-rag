"""BM25 retrieval over chunks.

Okapi BM25 is the standard lexical baseline for enterprise search: it needs
no GPU or embedding model, is explainable (a score is a sum over query terms)
and is still hard to beat on keyword-heavy corporate documents. The title and
section heading are indexed together with the text, so a query that names a
policy finds it even if the body uses other words.
"""

import math
from collections import Counter
from dataclasses import dataclass

from .corpus import Chunk
from .text import tokenize


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class BM25:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self._tf: list[Counter[str]] = []
        self._len: list[int] = []
        df: Counter[str] = Counter()
        for c in chunks:
            tokens = tokenize(f"{c.title} {c.section} {c.text}")
            tf = Counter(tokens)
            self._tf.append(tf)
            self._len.append(len(tokens))
            df.update(tf.keys())
        n = len(chunks)
        self._avg = sum(self._len) / n if n else 0.0
        # The "+1" variant keeps idf positive for terms present in most chunks.
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query_terms: list[str], i: int) -> float:
        tf, length = self._tf[i], self._len[i]
        s = 0.0
        for t in query_terms:
            f = tf.get(t)
            if f:
                norm = self.k1 * (1 - self.b + self.b * length / self._avg)
                s += self._idf[t] * f * (self.k1 + 1) / (f + norm)
        return s

    def search(self, query: str, k: int = 5, department: str | None = None) -> list[Hit]:
        terms = list(dict.fromkeys(tokenize(query)))
        if not terms:
            return []
        hits = []
        for i, c in enumerate(self.chunks):
            if department and c.department.lower() != department.lower():
                continue
            s = self.score(terms, i)
            if s > 0:
                hits.append(Hit(c, s))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]
