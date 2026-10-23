import pytest
from fastapi.testclient import TestClient

from conftest import CORPUS
from ragsearch import api


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("RAG_CORPUS", str(CORPUS))
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    api.get_rag.cache_clear()
    yield TestClient(api.app)
    api.get_rag.cache_clear()


def test_healthz(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert body["documents"] >= 10 and body["generator"] == "extractive"


def test_documents(client):
    docs = client.get("/api/documents").json()
    assert {"doc_id": "it-vpn-access", "title": "VPN Access Guide", "department": "IT"} in docs


def test_search(client):
    r = client.get("/api/search", params={"q": "vpn gateway not responding", "k": 2})
    results = r.json()["results"]
    assert r.status_code == 200 and len(results) <= 2
    assert results[0]["doc_id"] == "it-vpn-access" and results[0]["n"] == 1


def test_ask(client):
    r = client.post("/api/ask", json={"question": "How many quotes are needed above 5000 USD?"})
    body = r.json()
    assert r.status_code == 200
    assert "three competitive quotes" in body["answer"]
    assert body["sources"][0]["doc_id"] == "finance-procurement"


def test_ask_validation(client):
    assert client.post("/api/ask", json={"question": "x"}).status_code == 422
    assert client.get("/api/search", params={"q": "vpn", "k": 0}).status_code == 422


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200 and "Enterprise RAG Search" in r.text
