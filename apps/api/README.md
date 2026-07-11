# graphrag-api

FastAPI 0.115 + MCP server for GraphRAG Copilot v3.1.

## Endpoints

| route          | purpose                                            |
| -------------- | -------------------------------------------------- |
| `GET /healthz` | liveness check                                     |
| `GET /readyz`  | index and dependency readiness                     |
| `POST /v1/ask` | run the full LangGraph pipeline once               |
| `GET /v1/runs/{run_id}` | retrieve a stored run and its trace      |
| `/v1/mcp/sse`  | MCP SSE transport for external agent clients       |

## Run locally

```bash
GRAPHRAG_CORPUS_PATH=demo_docs \
  uv run --package graphrag-api uvicorn graphrag_api.main:app --reload --port 8000
```

From the repository root, `make api` supplies the same demo corpus default.
Run `make smoke` in a second terminal to check health, readiness, ask, and
stored-run contracts.

The MCP server is exposed at `/v1/mcp/sse`. Point Claude Desktop /
Cursor / any MCP-capable client at:

```
http://localhost:8000/v1/mcp/sse
```

## Tools exposed via MCP

| tool             | input                       | output                       |
| ---------------- | --------------------------- | ---------------------------- |
| search.vector    | `{ query, top_k }`          | `list[RetrievalHit]`         |
| search.bm25      | `{ query, top_k }`          | `list[RetrievalHit]`         |
| search.kg        | `{ query, top_k }`          | `list[RetrievalHit]`         |
| search.web       | `{ query, top_k }`          | `list[RetrievalHit]`         |
| orchestrate.ask  | `{ query }`                 | `{ answer, audit, trace }`   |
