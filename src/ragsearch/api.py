"""HTTP API and a one-page search UI.

    uvicorn ragsearch.api:app --port 8000

GET  /healthz              liveness + index size
GET  /api/documents        what is indexed
GET  /api/search?q=...     ranked chunks (retrieval only)
POST /api/ask              {"question": ..., "department": ...} -> grounded answer
"""

import logging
import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import __version__
from .corpus import load_corpus
from .generator import from_env
from .pipeline import RAG
from .retriever import Hit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="Enterprise RAG Search", version=__version__)


@lru_cache(maxsize=1)
def get_rag() -> RAG:
    corpus = os.environ.get("RAG_CORPUS", "data/corpus")
    return RAG(load_corpus(corpus), generator=from_env())


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    department: str | None = None


def source(n: int, h: Hit) -> dict:
    c = h.chunk
    return {
        "n": n,
        "doc_id": c.doc_id,
        "title": c.title,
        "section": c.section,
        "department": c.department,
        "score": round(h.score, 3),
        "text": c.text,
    }


@app.get("/healthz")
def healthz():
    rag = get_rag()
    return {
        "status": "ok",
        "version": __version__,
        "revision": os.environ.get("GIT_REVISION", "dev"),
        "documents": len(rag.docs),
        "chunks": len(rag.chunks),
        "generator": rag.generator.name,
    }


@app.get("/api/documents")
def documents():
    return [
        {"doc_id": d.doc_id, "title": d.title, "department": d.department} for d in get_rag().docs
    ]


@app.get("/api/search")
def search(
    q: str = Query(min_length=2, max_length=500),
    k: int = Query(5, ge=1, le=20),
    department: str | None = None,
):
    hits = get_rag().search(q, k, department)
    return {"query": q, "results": [source(n, h) for n, h in enumerate(hits, 1)]}


@app.post("/api/ask")
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(422, "empty question")
    a = get_rag().ask(req.question.strip(), req.department)
    return {
        "question": a.question,
        "answer": a.answer,
        "mode": a.mode,
        "latency_ms": a.latency_ms,
        "sources": [source(n, h) for n, h in enumerate(a.sources, 1)],
    }


_INDEX = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    return _INDEX
