# graphrag-observability

Langfuse tracing + audit export for GraphRAG Copilot v3.1.

## What you get

- One **trace** per agent run, opened by the orchestrator and tagged with
  the user query.
- One **span** per graph node (planner / retriever / evaluator /
  rewriter / generator / auditor / fallback), with input + output
  payloads attached.
- One **event** per emitted `AuditEntry` so the four custom v3.1 metrics
  can be computed offline from exported Langfuse runs.

## Safe no-op mode

If `LANGFUSE_PUBLIC_KEY` (or `LANGFUSE_SECRET_KEY`) is unset, the tracer
falls back to a no-op implementation. Unit tests + CI never need a live
Langfuse instance.

## Bring up Langfuse locally

```bash
docker compose -f infra/docker/docker-compose.dev.yml --env-file infra/docker/.env up -d langfuse langfuse-db
open http://localhost:3010
```

Log in, create a project, paste the public + secret keys into your env:

```bash
export LANGFUSE_PUBLIC_KEY=pk-lf-...
export LANGFUSE_SECRET_KEY=sk-lf-...
export LANGFUSE_HOST=http://localhost:3010
```
