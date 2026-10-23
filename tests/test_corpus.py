import pytest

from ragsearch.corpus import Document, chunk_document, parse_document
from ragsearch.text import stem, tokenize

RAW = """---
title: Test Policy
department: HR
---
# Test Policy

Intro line.

## First
alpha beta gamma

## Second
delta epsilon
"""


def test_tokenize_drops_stopwords_and_folds_forms():
    tokens = tokenize("What are the Policies for requested devices?")
    assert tokens == ["policy", "request", "device"]


@pytest.mark.parametrize(
    ("word", "expected"),
    [("policies", "policy"), ("working", "work"), ("days", "day"), ("access", "access"),
     ("status", "status"), ("vpn", "vpn")],
)
def test_stem(word, expected):
    assert stem(word) == expected


def test_parse_front_matter():
    doc = parse_document("test", RAW)
    assert doc.title == "Test Policy"
    assert doc.department == "HR"
    assert not doc.text.startswith("---")


def test_title_falls_back_to_heading():
    doc = parse_document("x", "# From Heading\n\ntext")
    assert doc.title == "From Heading"
    assert doc.department == "General"


def test_chunks_follow_sections():
    chunks = chunk_document(parse_document("test", RAW))
    assert [c.section for c in chunks] == ["Overview", "First", "Second"]
    assert chunks[1].text == "alpha beta gamma"
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_long_section_is_split_with_overlap():
    words = " ".join(f"w{i}" for i in range(250))
    doc = Document("long", "Long", f"## Body\n{words}")
    chunks = chunk_document(doc, max_words=100, overlap=20)
    assert [len(c.text.split()) for c in chunks] == [100, 100, 90]
    # The last 20 words of a chunk open the next one.
    assert chunks[0].text.split()[-20:] == chunks[1].text.split()[:20]


def test_bad_overlap():
    with pytest.raises(ValueError):
        chunk_document(Document("d", "D", "text"), max_words=10, overlap=10)


def test_corpus_loads(docs):
    assert len(docs) >= 10
    assert {d.department for d in docs} >= {"HR", "IT", "Finance", "Security"}
