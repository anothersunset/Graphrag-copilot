# graphrag-api

FastAPI 0.115 + MCP server for GraphRAG Copilot v3.1.

## Endpoints

| route          | purpose                                            |
| -------------- | -------------------------------------------------- |
| `GET /healthz` | liveness check                                     |
| `POST /v1/ask` | run the full LangGraph pipeline once               |
| `/v1/mcp/sse`  | MCP SSE transport for external agent clients       |

## Run locally

```bash
uv run --package graphrag-api uvicorn graphrag_api.app:app --reload --port 8000
```

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
