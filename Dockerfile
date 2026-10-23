# syntax=docker/dockerfile:1
# Three stages from one file:
#   base    - Python + pinned runtime dependencies (shared, cached layer)
#   test    - base + dev tools + the whole repo; CI runs lint, tests and evaluation in it
#   runtime - base + only the code and the knowledge base, non-root, with a health check
# `docker build .` builds runtime (the last stage); `--target test` builds the test image.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base AS test
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
CMD ["sh", "-c", "ruff check . && pytest --cov --cov-report=term"]

FROM base AS runtime
ARG GIT_REVISION=dev
LABEL org.opencontainers.image.title="enterprise-rag" \
      org.opencontainers.image.description="RAG system for intelligent enterprise search" \
      org.opencontainers.image.source="https://github.com/mkbdlnv/enterprise-rag" \
      org.opencontainers.image.revision=$GIT_REVISION
ENV RAG_CORPUS=/app/data/corpus \
    GIT_REVISION=$GIT_REVISION
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY src ./src
COPY data ./data
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
CMD ["uvicorn", "ragsearch.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
