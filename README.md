# enterprise-rag

Research prototype for the master's thesis **"Development of a Retrieval-Augmented Generation system for intelligent enterprise search"**, together with the DevOps setup that tests, packages and deploys it on every commit (Assignment 5: DevOps and CI/CD).

**Live demo:** https://rag.mkab.dev

## What it does

An employee asks a question in natural language ("How do I get VPN access?"). The system

1. **retrieves** the most relevant passages from the company knowledge base with Okapi BM25 (optionally filtered by department);
2. **guards** against hallucination: if nothing scores above a threshold, it says so instead of calling the model;
3. **generates** a short answer with an LLM (any OpenAI-compatible API, Gemini by default) that is instructed to use only the numbered sources and cite them as `[n]`;
4. **falls back** to an extractive answer (best-matching source sentences) when no key is configured or every model in the chain is busy, so the service always answers.

```
question ─► tokenize ─► BM25 over chunks ─► score ≥ threshold? ──no──► "not found"
                         (title+section+text)        │yes
                                                     ▼
                                   grounded prompt with sources [1..k]
                                                     │
                                   LLM chain (429/503/404 → next model)
                                                     │ all failed
                                                     ▼
                                        extractive answer with citations
```

The knowledge base (`data/corpus/`) is a set of Markdown policies of a fictional company (HR, IT, Finance, Security, Engineering, General). Each `##` section is a chunk; long sections are split into overlapping windows.

`data/eval.jsonl` is a labelled set of 30 questions. `python -m ragsearch.evaluate` reports **Recall@3** and **MRR**; the CI fails if retrieval quality drops below Recall@3 = 0.9 / MRR = 0.8.

## API

| | |
|---|---|
| `GET /` | search page |
| `GET /healthz` | status, revision, index size, generator in use |
| `GET /api/documents` | indexed documents |
| `GET /api/search?q=&k=&department=` | ranked chunks (retrieval only) |
| `POST /api/ask` `{"question", "department"?}` | answer, mode, latency, sources |

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=src uvicorn ragsearch.api:app --reload     # http://127.0.0.1:8000
pytest --cov                                          # 30 tests
PYTHONPATH=src python -m ragsearch.evaluate --k 3
```

With Docker:

```bash
docker build -t enterprise-rag .                      # runtime image
docker run --rm -p 8000:8000 -e LLM_API_KEY=... enterprise-rag
docker build --target test -t enterprise-rag:test . && docker run --rm enterprise-rag:test
```

Configuration is environment only, see [`app.env.example`](app.env.example).

## CI/CD

```
git push ─► GitHub ◄── Jenkins polls every 2 min (pollSCM)
                         │
  Checkout ─► Build test image ─► Lint (ruff) ─► Unit tests (pytest, JUnit + coverage)
          ─► Evaluate retrieval (Recall@3, MRR → artifact) ─► Build runtime image
          ─► [Push image, optional] ─► Deploy (health-check gate, auto-rollback) ─► Smoke test
                                            │
                              container "rag" on 127.0.0.1:8091 ─► nginx ─► https://rag.mkab.dev
```

- [`Dockerfile`](Dockerfile) — multi-stage: `base` (pinned deps), `test` (dev tools, used by CI), `runtime` (non-root, health check, only code + data).
- [`Jenkinsfile`](Jenkinsfile) — declarative pipeline above. The Jenkins agent needs only git and the Docker CLI; Python tooling lives in the test image.
- [`scripts/deploy.sh`](scripts/deploy.sh) — replaces the container, waits for the Docker health check, restores the previous image if the new one never becomes healthy. [`scripts/smoke.sh`](scripts/smoke.sh) — real requests against the deployed revision.
- [`jenkins/`](jenkins) — the Jenkins server as code: image with Docker CLI and plugins, [Configuration as Code](jenkins/casc.yaml) (admin user, LLM key credential, the pipeline job via Job DSL), compose file with a memory limit, and the one-time [`setup-server.sh`](jenkins/setup-server.sh).
- [`k8s/deployment.yaml`](k8s/deployment.yaml) — optional Kubernetes (Minikube/k3s) deployment with rolling updates and probes.

Jenkins listens on `127.0.0.1:8090` of the server only: `ssh -L 8090:127.0.0.1:8090 <server>` and open http://localhost:8090.

## Layout

```
src/ragsearch/   text.py (tokenizer), corpus.py (loading, chunking), retriever.py (BM25),
                 generator.py (LLM + extractive), pipeline.py (RAG), evaluate.py, api.py, index.html
data/            corpus/*.md, eval.jsonl
tests/           unit and API tests, retrieval-quality gate
docs/            assignment reports
```
