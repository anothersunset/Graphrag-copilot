"""Canonical FastAPI application for GraphRAG Copilot."""

from __future__ import annotations

import json
import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from graphrag_kg import Chunk, build_index
from pydantic import BaseModel, Field

from graphrag_api import __version__
from graphrag_api.assembly import build_orchestrator_from_index
from graphrag_api.config import settings
from graphrag_api.mcp.server import mount_mcp
from graphrag_api.run_store import RunStore
from graphrag_api.trace.retrieval_trace import RetrievalTraceExporter


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10_000)
    top_k: int = Field(default=5, ge=1, le=50)


class AskResponse(BaseModel):
    run_id: str
    query: str
    answer: str
    verdict: str
    confidence: float
    crag_decision: str
    cited_chunk_ids: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_trace: list[dict[str, Any]] = Field(default_factory=list)
    audit: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[dict[str, Any]] = Field(default_factory=list)
    query_history: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    evidence_pack: dict[str, Any] | None = None


def _load_corpus(path: Path) -> list[Chunk]:
    if not path.exists():
        raise FileNotFoundError(f"corpus path does not exist: {path}")
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    chunks: list[Chunk] = []
    for file in files:
        suffix = file.suffix.lower()
        if suffix in {".md", ".txt"}:
            content = file.read_text(encoding="utf-8").strip()
            if content:
                chunks.append(
                    Chunk(str(file.relative_to(path) if path.is_dir() else file.name), content)
                )
        elif suffix == ".jsonl":
            for line_no, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                content = str(row.get("content") or row.get("text") or "").strip()
                if content:
                    chunk_id = str(row.get("chunk_id") or f"{file.name}:{line_no}")
                    chunks.append(Chunk(chunk_id, content))
    if not chunks:
        raise ValueError(f"corpus contains no supported non-empty documents: {path}")
    return chunks


def _source_rows(state: dict[str, Any], cited_ids: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in state.get("fused_hits") or []:
        chunk_id = str(hit.get("chunk_id") or "")
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        rows.append(
            {
                "chunk_id": chunk_id,
                "content": str(hit.get("content") or ""),
                "source": str(hit.get("source") or "unknown"),
                "score": float(hit.get("rerank_score") or hit.get("score") or 0.0),
                "cited": chunk_id in cited_ids,
                "metadata": dict(hit.get("metadata") or {}),
            }
        )
    return rows


def create_app(
    *,
    orchestrator: Any | None = None,
    corpus_path: Path | None = None,
    api_key: str | None = None,
) -> FastAPI:
    effective_key = api_key if api_key is not None else settings.api_key
    if settings.env.lower() not in {"dev", "local", "test"} and not effective_key:
        raise RuntimeError("GRAPHRAG_API_KEY is required outside dev/local/test")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.orchestrator is None:
            selected_path = corpus_path or settings.corpus_path
            if selected_path is not None:
                try:
                    index = build_index(_load_corpus(selected_path))
                    app.state.orchestrator = build_orchestrator_from_index(index)
                    app.state.index_stats = {"chunks": len(index.chunk_texts), **index.stats()}
                    app.state.startup_error = None
                except Exception as exc:  # readiness exposes the safe summary
                    app.state.startup_error = str(exc)
        yield

    app = FastAPI(
        title="GraphRAG Copilot API",
        version=__version__,
        description="Agentic GraphRAG service with auditable evidence traces.",
        lifespan=lifespan,
    )
    app.state.orchestrator = orchestrator
    app.state.index_stats = None
    app.state.startup_error = None
    app.state.run_store = RunStore(
        capacity=settings.run_store_capacity,
        ttl_seconds=settings.run_store_ttl_seconds,
    )
    exporter = RetrievalTraceExporter()

    def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
        if effective_key is None:
            return
        if x_api_key is None or not secrets.compare_digest(x_api_key, effective_key):
            raise HTTPException(status_code=401, detail="invalid API key")

    def current_orchestrator() -> Any:
        value = app.state.orchestrator
        if value is None:
            raise HTTPException(
                status_code=503, detail={"code": "not_ready", "message": "index is not loaded"}
            )
        return value

    async def execute(req: AskRequest) -> AskResponse:
        orch = current_orchestrator()
        state = await orch.ainvoke({"question": req.query, "top_k": req.top_k})
        cited_ids = {str(chunk_id) for chunk_id in (state.get("cited_chunk_ids") or []) if chunk_id}
        trace = exporter.export(
            hits=state.get("hits") or [],
            fused=state.get("fused_hits") or [],
            cited_ids=sorted(cited_ids),
            query_history=state.get("query_rewrites") or [],
        )
        sources = _source_rows(state, cited_ids)
        confidence = float(
            state.get("crag_score") or max((row["score"] for row in sources), default=0.0)
        )
        result = AskResponse(
            run_id=f"run-{uuid.uuid4().hex}",
            query=req.query,
            answer=str(state.get("answer") or ""),
            verdict=str(state.get("auditor_verdict") or "fail"),
            confidence=max(0.0, min(1.0, confidence)),
            crag_decision=str(state.get("crag_decision") or "unknown"),
            cited_chunk_ids=sorted(cited_ids),
            sources=sources,
            retrieval_trace=trace,
            audit=[dict(item) for item in (state.get("audit") or [])],
            claims=[dict(item) for item in (state.get("claims") or [])],
            query_history=[str(item) for item in (state.get("query_rewrites") or [])],
            tool_calls=[dict(item) for item in (state.get("tool_calls") or [])],
            evidence_pack=state.get("evidence_pack"),
        )
        app.state.run_store.put(result.run_id, result.model_dump())
        return result

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, Any]:
        return {"status": "ok", "version": __version__, "env": settings.env}

    @app.get("/readyz", tags=["health"])
    async def readyz() -> Response:
        ready = app.state.orchestrator is not None
        body = {
            "status": "ready" if ready else "not_ready",
            "version": __version__,
            "env": settings.env,
            "dependencies": {
                "orchestrator": {"status": "ok" if ready else "not_configured"},
                "index": app.state.index_stats,
            },
        }
        if app.state.startup_error:
            body["error"] = app.state.startup_error
        return JSONResponse(body, status_code=200 if ready else 503)

    @app.post("/v1/ask", response_model=AskResponse, dependencies=[Depends(require_api_key)])
    @app.post(
        "/api/query",
        response_model=AskResponse,
        deprecated=True,
        dependencies=[Depends(require_api_key)],
    )
    async def ask(req: AskRequest, request: Request, response: Response) -> AskResponse:
        if request.url.path.startswith("/api/"):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "Wed, 31 Dec 2026 23:59:59 GMT"
        return await execute(req)

    async def event_stream(req: AskRequest) -> AsyncIterator[str]:
        yield f"data: {json.dumps({'type': 'phase', 'phase': 'orchestrating'})}\n\n"
        try:
            result = await execute(req)
            yield f"data: {json.dumps({'type': 'answer_start'})}\n\n"
            if result.answer:
                yield f"data: {json.dumps({'type': 'token', 'text': result.answer})}\n\n"
            yield f"data: {json.dumps({'type': 'answer_end'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'data': result.model_dump()})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    @app.post("/v1/ask/stream", dependencies=[Depends(require_api_key)])
    @app.post("/api/query/stream", deprecated=True, dependencies=[Depends(require_api_key)])
    async def ask_stream(req: AskRequest, request: Request) -> StreamingResponse:
        headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        if request.url.path.startswith("/api/"):
            headers.update({"Deprecation": "true", "Sunset": "Wed, 31 Dec 2026 23:59:59 GMT"})
        return StreamingResponse(event_stream(req), media_type="text/event-stream", headers=headers)

    @app.get(
        "/v1/runs/{run_id}", response_model=AskResponse, dependencies=[Depends(require_api_key)]
    )
    async def get_run(run_id: str) -> AskResponse:
        value = app.state.run_store.get(run_id)
        if value is None:
            raise HTTPException(status_code=404, detail="run not found or expired")
        return AskResponse.model_validate(value)

    mount_mcp(
        app,
        orchestrator_provider=lambda: app.state.orchestrator,
        api_key=effective_key,
    )
    return app


app = create_app()
