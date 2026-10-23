"""Loading the knowledge base and cutting it into retrievable chunks.

A document is a Markdown file with a small front matter block:

    ---
    title: Remote Work Policy
    department: HR
    ---
    # Remote Work Policy
    ## Eligibility
    ...

Each `##` section is chunked separately so that a chunk never mixes two
topics; long sections are split into overlapping word windows.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    text: str
    meta: dict[str, str] = field(default_factory=dict)

    @property
    def department(self) -> str:
        return self.meta.get("department", "General")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    department: str
    text: str


_FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_document(doc_id: str, raw: str) -> Document:
    meta: dict[str, str] = {}
    m = _FRONT.match(raw)
    if m:
        for line in m.group(1).splitlines():
            key, sep, value = line.partition(":")
            if sep:
                meta[key.strip().lower()] = value.strip()
        raw = raw[m.end() :]
    title = meta.get("title")
    if not title:
        h1 = re.search(r"^# (.+)$", raw, re.MULTILINE)
        title = h1.group(1).strip() if h1 else doc_id
    return Document(doc_id=doc_id, title=title, text=raw.strip(), meta=meta)


def load_corpus(directory: str | Path) -> list[Document]:
    paths = sorted(Path(directory).glob("*.md"))
    if not paths:
        raise FileNotFoundError(f"no .md documents in {directory}")
    return [parse_document(p.stem, p.read_text(encoding="utf-8")) for p in paths]


def _sections(text: str) -> list[tuple[str, str]]:
    """(heading, body) pairs; text before the first `##` goes under "Overview"."""
    out: list[tuple[str, str]] = []
    heading, lines = "Overview", []
    for line in text.splitlines():
        if line.startswith("## "):
            out.append((heading, "\n".join(lines)))
            heading, lines = line[3:].strip(), []
        elif not line.startswith("# "):
            lines.append(line)
    out.append((heading, "\n".join(lines)))
    return [(h, b.strip()) for h, b in out if b.strip()]


def chunk_document(doc: Document, max_words: int = 120, overlap: int = 30) -> list[Chunk]:
    if not 0 <= overlap < max_words:
        raise ValueError("overlap must be in [0, max_words)")
    chunks: list[Chunk] = []
    for heading, body in _sections(doc.text):
        words = body.split()
        start = 0
        while True:
            window = words[start : start + max_words]
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}#{len(chunks)}",
                    doc_id=doc.doc_id,
                    title=doc.title,
                    section=heading,
                    department=doc.department,
                    text=" ".join(window),
                )
            )
            if start + max_words >= len(words):
                break
            start += max_words - overlap
    return chunks


def chunk_corpus(docs: list[Document], max_words: int = 120, overlap: int = 30) -> list[Chunk]:
    return [c for d in docs for c in chunk_document(d, max_words, overlap)]
