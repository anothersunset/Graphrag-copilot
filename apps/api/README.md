# graphrag-api

FastAPI service for graphrag-copilot.

## Run

```bash
uv run uvicorn graphrag_api.main:app --reload --port 8000
# or from repo root:
make api
```

Then visit:
- http://localhost:8000/healthz — liveness
- http://localhost:8000/readyz — readiness
- http://localhost:8000/docs — OpenAPI / Swagger UI

## Test

```bash
uv run pytest apps/api/tests -v
```
