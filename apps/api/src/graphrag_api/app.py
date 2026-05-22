"""FastAPI application factory."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from .mcp.server import build_mcp_app
from .trace.retrieval_trace import RetrievalTraceExporter


class AskRequest(BaseModel):
    query: str
    user_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    audit: list[dict]
    retrieval_trace: list[dict]
    tool_calls: list[dict]


def get_orchestrator() -> Any:
    """Default orchestrator factory — overridden in tests."""
    from graphrag_graph.graph import build_graph

    return build_graph()


def get_trace_exporter() -> RetrievalTraceExporter:
    return RetrievalTraceExporter()


def create_app(
    *,
    orchestrator_factory=get_orchestrator,
    trace_factory=get_trace_exporter,
) -> FastAPI:
    app = FastAPI(title="GraphRAG Copilot API", version="0.1.0")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "version": "0.1.0"}

    @app.post("/v1/ask", response_model=AskResponse)
    def ask(
        req: AskRequest,
        orchestrator=Depends(orchestrator_factory),
        exporter: RetrievalTraceExporter = Depends(trace_factory),
    ):
        result = orchestrator.invoke({"query": req.query})
        return AskResponse(
            answer=result.get("answer", ""),
            audit=[_to_dict(e) for e in result.get("audit", [])],
            retrieval_trace=exporter.export(
                hits=result.get("hits", []),
                fused=result.get("fused_hits", []),
                cited_ids=result.get("cited_chunk_ids", []),
            ),
            tool_calls=[_to_dict(tc) for tc in result.get("tool_calls", [])],
        )

    # Mount MCP SSE server.
    mcp_app = build_mcp_app()
    app.mount("/v1/mcp", mcp_app)

    return app


def _to_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {"value": str(obj)}


app = create_app()
