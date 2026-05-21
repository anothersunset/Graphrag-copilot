"""FastMCP server wiring — mounted under /v1/mcp by app.py."""
from __future__ import annotations

import logging
from typing import Any

from .tools import TOOL_REGISTRY, ToolSpec

logger = logging.getLogger(__name__)


def build_mcp_app(*, orchestrator: Any | None = None) -> Any:
    """Build an MCP-compatible ASGI sub-app.

    Falls back to a tiny stub ASGI app if the official mcp SDK is not
    installed (lets unit tests load app.py without the heavy dep).
    """
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ImportError:
        logger.warning("mcp SDK not installed; mounting stub /v1/mcp")
        return _stub_app()

    mcp = FastMCP("graphrag-copilot")

    for spec in TOOL_REGISTRY.values():
        _register_tool(mcp, spec, orchestrator=orchestrator)

    return mcp.sse_app()


def _register_tool(mcp: Any, spec: ToolSpec, *, orchestrator: Any) -> None:
    name = spec.name

    async def _handler(**kwargs):
        if name.startswith("search."):
            return {
                "hits": _stub_hits(query=kwargs.get("query", ""), source=name.split(".", 1)[1])
            }
        if name == "orchestrate.ask" and orchestrator is not None:
            return orchestrator.invoke({"query": kwargs.get("query", "")})
        return {"answer": "stub", "audit": [], "retrieval_trace": [], "tool_calls": []}

    _handler.__name__ = name.replace(".", "_")
    _handler.__doc__ = spec.description
    mcp.tool(name=name, description=spec.description)(_handler)


def _stub_hits(*, query: str, source: str) -> list[dict]:
    return [
        {
            "chunk_id": f"{source}:stub:0",
            "source": source,
            "score": 0.5,
            "rerank_score": None,
            "content": f"stub {source} hit for {query!r}",
            "metadata": {},
        }
    ]


def _stub_app():
    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 503, "headers": []})
        await send({"type": "http.response.body", "body": b"mcp sdk not installed"})

    return app
