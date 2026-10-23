from pathlib import Path

import pytest

from ragsearch.corpus import load_corpus
from ragsearch.pipeline import RAG

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"
EVAL = ROOT / "data" / "eval.jsonl"


@pytest.fixture(scope="session")
def docs():
    return load_corpus(CORPUS)


@pytest.fixture(scope="session")
def rag(docs):
    return RAG(docs)
