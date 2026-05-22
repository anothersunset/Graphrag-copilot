"""FastAPI app exposing /v1/ask and the MCP server at /v1/mcp."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from .mcp.server import mount_mcp
from .trace.retrieval_trace import RetrievalTraceExporter

logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    query: str
    top_k: int = 5


class AskResponse(BaseModel):
    answer: str
    verdict: str
    cited_chunk_ids: list[str]
    audit: list[dict]
    retrieval_trace: list[dict]
    claims: list[dict] = []
    query_history: list[str] = []
    evidence_pack: dict | None = None


def _default_orchestrator():
    """Late-bound import so the package boots without graph dependencies."""
    from graphrag_graph.app import build_graph  # type: ignore

    return build_graph()


def _default_exporter() -> RetrievalTraceExporter:
    return RetrievalTraceExporter()


def get_orchestrator():  # FastAPI dependency override target
    return _default_orchestrator()


def get_exporter() -> RetrievalTraceExporter:  # FastAPI dependency override target
    return _default_exporter()


def create_app() -> FastAPI:
    app = FastAPI(title="graphrag-copilot", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/ask", response_model=AskResponse)
    async def ask(
        req: AskRequest,
        orchestrator: Any = Depends(get_orchestrator),
        exporter: RetrievalTraceExporter = Depends(get_exporter),
    ) -> AskResponse:
        state = await orchestrator.ainvoke({"question": req.query, "top_k": req.top_k})
        trace = exporter.export(
            hits=state.get("hits") or [],
            fused=state.get("fused_hits") or [],
            cited_ids=state.get("cited_chunk_ids") or [],
            query_history=state.get("query_rewrites") or [],
        )
        return AskResponse(
            answer=state.get("answer", ""),
            verdict=state.get("verdict", "unsupported"),
            cited_chunk_ids=state.get("cited_chunk_ids") or [],
            audit=[a if isinstance(a, dict) else a.__dict__ for a in (state.get("audit") or [])],
            retrieval_trace=trace,
            claims=state.get("claims") or [],
            query_history=state.get("query_rewrites") or [],
            evidence_pack=state.get("evidence_pack"),
        )

    mount_mcp(app)
    return app


app = create_app()
