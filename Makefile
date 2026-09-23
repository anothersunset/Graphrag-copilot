.PHONY: help install dev test lint fmt typecheck clean api web ingest docker-build ci-activate smoke

GRAPHRAG_CORPUS_PATH ?= demo_docs
BASE_URL ?= http://127.0.0.1:8000
export GRAPHRAG_CORPUS_PATH
export BASE_URL

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS=":.*?##"} {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## Install all deps (uv + pnpm)
	uv sync --all-packages --dev
	pnpm install --frozen-lockfile

api:  ## Run FastAPI dev server on :8000
	uv run --package graphrag-api uvicorn graphrag_api.main:app --reload --port 8000

ingest:  ## Provision retrieval artifacts: make ingest ARGS="--corpus demo_docs"
	uv run --package graphrag-api python -m graphrag_api.ingest $(ARGS)

web:  ## Run Next.js dev server on :3000
	pnpm --filter @graphrag/web dev

dev:  ## Run api + web concurrently (requires GNU make)
	@$(MAKE) -j 2 api web

test:  ## Run all Python tests with coverage
	uv run pytest --cov --cov-report=term-missing --cov-report=xml

lint:  ## Lint Python (ruff) + frontend (biome)
	uv run ruff check .
	pnpm lint

fmt:  ## Format Python (ruff) + frontend (biome)
	uv run ruff format .
	uv run ruff check --fix .
	pnpm format

typecheck:  ## Run pyright + tsc
	uv run pyright
	pnpm typecheck

smoke:  ## Run API smoke checks against BASE_URL (default http://localhost:8000)
	uv run python test_api.py

docker-build:  ## Build api + web Docker images
	docker compose build

ci-activate:  ## Render workflow templates into .github/workflows/ (run once after clone)
	bash scripts/install-workflows.sh

clean:  ## Remove caches
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
	cd apps/web && rm -rf .next node_modules
