# ADR-0002 · Monorepo container for `apps/*` and `packages/*`

- **Status:** Accepted
- **Date:** 2026-05-21
- **Deciders:** lee fanwei
- **Supersedes:** —
- **Refines:** [ADR-0001](./0001-from-v1-to-v3.1.md) §4

## Context

v1 was a flat `backend/` + `frontend/` layout. v3.1 needs to publish 7 reusable Python packages (`schemas`, `retriever`, `reranker`, `kg`, `graph`, `observability`, `evals`) plus 2 deployable apps (`apps/api`, `apps/web`). Three layouts considered:

| Option | Pros | Cons |
|---|---|---|
| Flat (v1) | Simple | No clean package boundaries; hard to test in isolation; circular imports |
| Multi-repo | Strong isolation | 8 repos to maintain for a solo project = unsustainable |
| **Monorepo** (chosen) | Single CI, single PR; cross-package refactors atomic; uv + pnpm both support workspaces natively | Slightly more config |

## Decision

Adopt a **uv + pnpm monorepo**:

```
graphrag-copilot/
├── apps/
│   ├── api/         # FastAPI service
│   └── web/         # Next.js 15
├── packages/
│   ├── schemas/     # Pydantic models (the hub)
│   ├── retriever/   # 4-way hybrid retrieval
│   ├── reranker/    # BGE-Reranker-v2-m3 wrapper
│   ├── kg/          # Neo4j subgraph + 3-hop expansion
│   ├── graph/       # LangGraph 7-node orchestrator
│   ├── observability/ # Langfuse + RetrievalTrace emitter
│   └── evals/       # RAGAS + DeepEval + 4 custom metrics
├── backend/         # v1 legacy — kept until W4 D1 migration cutoff
├── frontend/        # v1 legacy — kept until W6 D1 migration cutoff
├── eval/            # v1 legacy harness — kept until W5 D1
├── docs/
├── pyproject.toml   # uv workspace root
├── pnpm-workspace.yaml
├── Makefile
└── .pre-commit-config.yaml
```

## Migration plan

- **W1 (this PR)**: empty `apps/*` + `packages/*` scaffolding alongside `backend/` etc. Both coexist.
- **W2-W4**: write new code in `packages/*`; reference v1 modules read-only.
- **W4 D1**: migrate `backend/document_parser` + `evidence_fusion` → `packages/retriever` + `packages/schemas`.
- **W5 D1**: migrate `eval/` → `packages/evals`.
- **W6 D1**: migrate `frontend/` → `apps/web` (clean cut, not file-by-file).
- **W7 D7**: delete `backend/` + `frontend/` + `eval/` (legacy).

## Consequences

**Positive**
- One `git clone` → one `make install` → one `make test` runs everything.
- Cross-package refactors are atomic (e.g., changing `RetrievalTrace` schema updates all consumers in one PR).
- Single CI run validates the whole stack.

**Negative**
- Slightly slower CI (mitigated by `uv` cache + `pnpm` cache + path-based workflow triggers).
- Newcomers must learn uv workspaces (mitigated by `make help`).

**Neutral**
- `pyright strict` deferred to W7 because empty placeholder `__init__.py` files trip strict mode without value during scaffolding.

## Validation

This ADR is validated when:
- [ ] CI green on `feat/monorepo-skeleton` (Python + Frontend workflows)
- [ ] `make install && make test` passes locally
- [ ] PR merged to `main` with linear history
