# graphrag-api — FastAPI + MCP server image.
#
# Multi-stage: a uv builder resolves the workspace for the graphrag-api
# member (plus its workspace deps: schemas/retrieval/parsers/kg/graph/
# observability), then a slim runtime copies the venv + sources at the
# same layout (workspace members install editable, so paths must match).
# The demo corpus ships in-image so the container boots into a working
# GraphRAG with zero configuration; index artifacts and the run store
# persist to /data (mount a volume there).

# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY apps/api ./apps/api
COPY packages ./packages
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package graphrag-api --no-dev

FROM python:3.12-slim-bookworm AS runtime
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    GRAPHRAG_CORPUS_PATH=/app/examples/demo_docs \
    GRAPHRAG_INDEX_PATH=/data/index.json \
    GRAPHRAG_RUN_STORE_URL=sqlite:////data/runs.db
COPY --from=builder --chown=root:root /app /app
COPY --chown=appuser:appuser examples/demo_docs /app/examples/demo_docs
RUN mkdir -p /data && chown appuser:appuser /data
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)"]
CMD ["python", "-m", "uvicorn", "graphrag_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
