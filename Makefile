.PHONY: help install dev test lint fmt typecheck clean api web docker-build

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS=":.*?##"} {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## Install all deps (uv + pnpm)
	uv sync --all-packages --dev
	cd apps/web && pnpm install

api:  ## Run FastAPI dev server on :8000
	cd apps/api && uv run uvicorn graphrag_api.main:app --reload --port 8000

web:  ## Run Next.js dev server on :3000
	cd apps/web && pnpm dev

dev:  ## Run api + web concurrently (requires GNU make)
	@$(MAKE) -j 2 api web

test:  ## Run all Python tests with coverage
	uv run pytest --cov --cov-report=term-missing --cov-report=xml

lint:  ## Lint Python (ruff) + frontend (biome)
	uv run ruff check .
	cd apps/web && pnpm biome check src

fmt:  ## Format Python (ruff) + frontend (biome)
	uv run ruff format .
	uv run ruff check --fix .
	cd apps/web && pnpm biome format --write src

typecheck:  ## Run pyright + tsc
	uv run pyright
	cd apps/web && pnpm typecheck

docker-build:  ## Build api + web Docker images
	docker compose build

clean:  ## Remove caches
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml htmlcov
	find . -type d -name __pycache__ -exec rm -rf {} +
	cd apps/web && rm -rf .next node_modules
