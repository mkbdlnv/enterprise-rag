"""Retrieve -> (guard) -> generate."""

import logging
import time
from dataclasses import dataclass

from .corpus import Document, chunk_corpus
from .generator import ExtractiveGenerator, Generator, LLMError
from .retriever import BM25, Hit

log = logging.getLogger("ragsearch")

NOT_FOUND = "I could not find this in the knowledge base."


@dataclass
class Answer:
    question: str
    answer: str
    mode: str
    sources: list[Hit]
    latency_ms: int


class RAG:
    def __init__(
        self,
        docs: list[Document],
        generator: Generator | None = None,
        k: int = 4,
        min_score: float = 1.0,
    ):
        self.docs = docs
        self.chunks = chunk_corpus(docs)
        self.retriever = BM25(self.chunks)
        self.generator = generator or ExtractiveGenerator()
        self.fallback = ExtractiveGenerator()
        self.k = k
        # Below this BM25 score a hit shares only a stop-word-like term with the
        # query; sending such context to a model invites a made-up answer.
        self.min_score = min_score

    def search(self, query: str, k: int | None = None, department: str | None = None) -> list[Hit]:
        hits = self.retriever.search(query, k or self.k, department)
        return [h for h in hits if h.score >= self.min_score]

    def ask(self, question: str, department: str | None = None) -> Answer:
        t0 = time.perf_counter()
        hits = self.search(question, department=department)
        if not hits:
            text, mode = NOT_FOUND, "no-context"
        else:
            try:
                text, mode = self.generator.generate(question, hits), self.generator.name
            except LLMError as e:
                log.warning("llm failed, answering extractively: %s", e)
                text, mode = self.fallback.generate(question, hits), "extractive-fallback"
        ms = int((time.perf_counter() - t0) * 1000)
        return Answer(question, text, mode, hits, ms)
