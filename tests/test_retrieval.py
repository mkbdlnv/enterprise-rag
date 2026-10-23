import json
import urllib.error

import pytest

from conftest import EVAL
from ragsearch.evaluate import evaluate, load_eval
from ragsearch.generator import ExtractiveGenerator, LLMError, LLMGenerator
from ragsearch.pipeline import NOT_FOUND, RAG


def test_top_hit_is_the_right_document(rag):
    hits = rag.search("how many vacation days per year")
    assert hits[0].chunk.doc_id == "hr-leave-policy"
    assert hits == sorted(hits, key=lambda h: h.score, reverse=True)


def test_department_filter(rag):
    hits = rag.search("approval", k=20, department="finance")
    assert hits and all(h.chunk.department == "Finance" for h in hits)


def test_nothing_for_unrelated_or_empty_query(rag):
    assert rag.search("the and of") == []
    assert rag.search("quantum chromodynamics") == []


def test_retrieval_quality_does_not_regress(rag):
    """The CI gate: a change that breaks retrieval fails the build."""
    report = evaluate(rag, load_eval(EVAL), k=3)
    assert report["recall@3"] >= 0.9, report["misses"]
    assert report["mrr"] >= 0.8


def test_extractive_answer_cites_source(rag):
    a = rag.ask("What is the per diem for international trips?")
    assert a.mode == "extractive"
    assert "70 USD" in a.answer
    assert "[1]" in a.answer


def test_no_context_skips_generation(docs):
    class Boom:
        name = "boom"

        def generate(self, question, hits):
            raise AssertionError("must not be called without context")

    a = RAG(docs, generator=Boom()).ask("quantum chromodynamics")
    assert (a.answer, a.mode, a.sources) == (NOT_FOUND, "no-context", [])


class FakeResponse:
    def __init__(self, text):
        self.body = json.dumps({"choices": [{"message": {"content": text}}]}).encode()

    def read(self, *_):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_llm_generator_sends_grounded_prompt(monkeypatch, rag):
    sent = {}

    def fake_urlopen(req, timeout):
        sent["url"] = req.full_url
        sent["body"] = json.loads(req.data)
        return FakeResponse("You get 24 days [1].")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    gen = LLMGenerator("key", "https://llm.example/v1/", ["m1"])
    hits = rag.search("vacation days")
    assert gen.generate("vacation days?", hits) == "You get 24 days [1]."
    assert sent["url"] == "https://llm.example/v1/chat/completions"
    user = sent["body"]["messages"][1]["content"]
    assert "[1] Annual Leave" in user and "Question: vacation days?" in user


def test_llm_falls_through_busy_model(monkeypatch, rag):
    calls = []

    def fake_urlopen(req, timeout):
        model = json.loads(req.data)["model"]
        calls.append(model)
        if model == "busy":
            raise urllib.error.HTTPError(req.full_url, 429, "busy", {}, None)
        return FakeResponse("ok")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    gen = LLMGenerator("key", "https://x", ["busy", "spare"])
    assert gen.generate("q", rag.search("vacation")) == "ok"
    assert calls == ["busy", "spare"] and gen.last_model == "spare"


def test_pipeline_falls_back_when_llm_is_down(monkeypatch, docs):
    def down(req, timeout):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr("urllib.request.urlopen", down)
    rag = RAG(docs, generator=LLMGenerator("key", "https://x", ["m"]))
    a = rag.ask("How long must my password be?")
    assert a.mode == "extractive-fallback"
    assert "14 characters" in a.answer


def test_llm_error_when_all_models_fail(monkeypatch, rag):
    def bad(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", bad)
    with pytest.raises(LLMError):
        LLMGenerator("key", "https://x", ["a", "b"]).generate("q", rag.search("vacation"))


def test_extractive_without_overlap():
    assert ExtractiveGenerator().generate("zzz", []) == NOT_FOUND
