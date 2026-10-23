"""Retrieval quality on a labelled question set: Recall@k and MRR.

    python -m ragsearch.evaluate --k 3

Each line of the eval file is {"question": ..., "doc_id": ...} — the document
that answers it. A question counts as found at rank r if any chunk of that
document is the r-th distinct document returned. The JSON on stdout is
archived by CI, so a change that hurts retrieval is visible build to build.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from .corpus import load_corpus
from .pipeline import RAG


def load_eval(path: str | Path) -> list[dict]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def evaluate(rag: RAG, items: list[dict], k: int = 3) -> dict:
    found, rr, misses = 0, 0.0, []
    for item in items:
        ranked: list[str] = []
        for h in rag.retriever.search(item["question"], k=50):
            if h.chunk.doc_id not in ranked:
                ranked.append(h.chunk.doc_id)
        rank = ranked.index(item["doc_id"]) + 1 if item["doc_id"] in ranked else None
        if rank and rank <= k:
            found += 1
        else:
            misses.append({"question": item["question"], "expected": item["doc_id"],
                           "got": ranked[:k]})
        if rank:
            rr += 1 / rank
    n = len(items)
    return {
        "questions": n,
        "k": k,
        f"recall@{k}": round(found / n, 4),
        "mrr": round(rr / n, 4),
        "documents": len(rag.docs),
        "chunks": len(rag.chunks),
        "misses": misses,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--corpus", default=os.environ.get("RAG_CORPUS", "data/corpus"))
    p.add_argument("--eval", default=os.environ.get("RAG_EVAL", "data/eval.jsonl"))
    p.add_argument("--k", type=int, default=3)
    args = p.parse_args(argv)
    report = evaluate(RAG(load_corpus(args.corpus)), load_eval(args.eval), args.k)
    json.dump(report, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
