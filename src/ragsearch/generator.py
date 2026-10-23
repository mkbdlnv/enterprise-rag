"""Answer generation from retrieved chunks.

`LLMGenerator` calls any OpenAI-compatible chat completions API (Gemini,
OpenAI, a local vLLM/Ollama server) with a grounded prompt: answer only from
the numbered sources and cite them as [n]. `ExtractiveGenerator` needs no
model at all: it returns the source sentences that overlap the question most.
It is the fallback when no key is configured or the model is unavailable, so
the service always answers and tests never need the network.
"""

import json
import os
import re
import urllib.error
import urllib.request
from typing import Protocol

from .retriever import Hit
from .text import tokenize

SYSTEM_PROMPT = """You are an enterprise search assistant. Answer the employee's question \
using ONLY the numbered sources below. Cite every fact with its source number in square \
brackets, e.g. [1] or [2][3]. If the sources do not contain the answer, reply exactly: \
"I could not find this in the knowledge base." Be concise: at most 4 sentences."""


def format_context(hits: list[Hit]) -> str:
    return "\n\n".join(
        f"[{n}] {h.chunk.title} — {h.chunk.section}\n{h.chunk.text}" for n, h in enumerate(hits, 1)
    )


class Generator(Protocol):
    name: str

    def generate(self, question: str, hits: list[Hit]) -> str: ...


class ExtractiveGenerator:
    name = "extractive"

    def __init__(self, max_sentences: int = 2):
        self.max_sentences = max_sentences

    def generate(self, question: str, hits: list[Hit]) -> str:
        q = set(tokenize(question))
        scored = []
        for n, h in enumerate(hits, 1):
            for pos, sentence in enumerate(re.split(r"(?<=[.!?])\s+", h.chunk.text)):
                overlap = len(q & set(tokenize(sentence)))
                if overlap:
                    # Earlier sources and earlier sentences win ties.
                    scored.append((-overlap, n, pos, sentence.strip(), n))
        if not scored:
            return "I could not find this in the knowledge base."
        best = sorted(scored)[: self.max_sentences]
        return " ".join(f"{s} [{n}]" for *_, s, n in best)


class LLMError(RuntimeError):
    pass


class LLMGenerator:
    name = "llm"

    def __init__(self, api_key: str, base_url: str, models: list[str], timeout: float = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.models = models
        self.timeout = timeout
        self.last_model: str | None = None

    def _ask(self, model: str, question: str, hits: list[Hit]) -> str:
        body = {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Sources:\n{format_context(hits)}\n\nQuestion: {question}",
                },
            ],
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.load(resp)
        return data["choices"][0]["message"]["content"].strip()

    def generate(self, question: str, hits: list[Hit]) -> str:
        """Tries the models in order: a busy (429/503) or missing (404) model
        hands over to the next one."""
        last: Exception | None = None
        for model in self.models:
            try:
                text = self._ask(model, question, hits)
                self.last_model = model
                return text
            except urllib.error.HTTPError as e:
                last = e
                if e.code not in (404, 429, 500, 503):
                    break
            except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
                last = e
        raise LLMError(f"all models failed: {last}")


def from_env() -> Generator:
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        return ExtractiveGenerator()
    return LLMGenerator(
        api_key=key,
        base_url=os.environ.get(
            "LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"
        ),
        models=[
            m.strip()
            for m in os.environ.get(
                "LLM_MODEL", "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-2.5-flash-lite"
            ).split(",")
            if m.strip()
        ],
    )
