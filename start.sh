#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

export GRAPHRAG_CORPUS_PATH="${GRAPHRAG_CORPUS_PATH:-$ROOT_DIR/demo_docs}"
exec uv run --package graphrag-api \
  uvicorn graphrag_api.main:app --reload --host 0.0.0.0 --port "${GRAPHRAG_API_PORT:-8000}"
