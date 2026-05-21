# CI workflow templates

These YAML files are the **canonical CI workflow definitions** for graphrag-copilot.
They live here instead of `.github/workflows/` because the **Notion GitHub MCP integration's underlying GitHub App does not declare `workflows:write` scope** — so the AI agent cannot push to `.github/workflows/*` itself.

## One-time activation

Run this once from a local clone (30 seconds):

```bash
git pull origin feat/monorepo-skeleton  # or main once merged
mkdir -p .github/workflows
git mv docs/ci-templates/ci-python.yml     .github/workflows/ci-python.yml
git mv docs/ci-templates/ci-frontend.yml   .github/workflows/ci-frontend.yml
git mv docs/ci-templates/ci-docs.yml       .github/workflows/ci-docs.yml
git commit -m "ci: activate workflows by moving from docs/ci-templates/"
git push
```

Alternatively, in the GitHub web UI: open each YAML → click the pencil icon ("Edit") → change the path prefix in the filename field from `docs/ci-templates/` to `.github/workflows/` → "Commit changes". Repeat for all 3.

## Why not just use the GitHub web UI to create them?

You can. The above `git mv` is just the lowest-friction approach. Either path completes in under 2 minutes.

## Future workflows

W2 (docker-build), W5 (ragas-eval), W8 (release-please) will land here first too. We will reuse this `git mv` step each time — it is a known boundary, not a defect.

## Why this is acceptable engineering

- The YAMLs themselves are versioned in git from day one.
- The migration step is reproducible and explicit.
- The boundary is documented in [ADR-0002](../adr/0002-monorepo-container.md) (Neutral consequences section to be updated when activated).
