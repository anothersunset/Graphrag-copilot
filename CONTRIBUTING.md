# Contributing to graphrag-copilot

Thanks for your interest. This project ships in **8 weeks** (2026-05-21 → 2026-07-16) under the v3.1 spec.
If you are reviewing for a hiring decision, read [`docs/adr/0001-from-v1-to-v3.1.md`](docs/adr/0001-from-v1-to-v3.1.md) first.

## Local setup

Prereqs: Python 3.12 · Node 22 · uv 0.4+ · pnpm 9 · Docker.

```bash
git clone https://github.com/anothersunset/Graphrag-copilot.git
cd Graphrag-copilot
make install        # uv sync + pnpm install
make dev            # api on :8000, web on :3000
make test           # pytest with coverage
make lint typecheck # ruff + pyright + biome + tsc
```

## Branch & commit conventions

- Branch: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, `chore/<topic>`.
- Commit: [Conventional Commits](https://www.conventionalcommits.org/). Examples:
  - `feat(retriever): add BGE-Reranker-v2-m3 second stage`
  - `fix(graph): handle empty CRAG fallback (#42)`
  - `docs(adr): add 0003 contextual retrieval decision`
- One logical change per PR. Squash on merge.

## PR checklist

- [ ] CI green (Python + Frontend + Docs)
- [ ] New code has tests (target ≥ 70% diff coverage from W5)
- [ ] Public APIs typed (`pyright basic` now, `strict` from W7)
- [ ] ADR added when introducing a new tech or architecture change
- [ ] CHANGELOG `[Unreleased]` updated

## Architecture invariants (do not break)

1. **Every retrieval emits a `RetrievalTrace`** — see `packages/schemas/src/graphrag_schemas/retrieval_trace.py`.
2. **Every tool call goes through the `ToolSpec` registry** — no ad-hoc `requests.post(...)`.
3. **Every CRAG decision is logged** — `confidence_score` + `branch` + `rewrite_count`.
4. **No `git push --force` on `main`** — only on `feat/*` branches.

Thanks for keeping the quality bar high. 🍒
