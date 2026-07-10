"""FastMCP server wiring — mounted under /v1/mcp by app.py."""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from typing import Any

from .tools import TOOL_REGISTRY, ToolSpec

logger = logging.getLogger(__name__)


def build_mcp_app(
    *,
    orchestrator: Any | None = None,
    orchestrator_provider: Callable[[], Any | None] | None = None,
) -> Any:
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
        _register_tool(
            mcp,
            spec,
            orchestrator=orchestrator,
            orchestrator_provider=orchestrator_provider,
        )

    return mcp.sse_app()


def _register_tool(
    mcp: Any,
    spec: ToolSpec,
    *,
    orchestrator: Any,
    orchestrator_provider: Callable[[], Any | None] | None,
) -> None:
    name = spec.name

    async def _handler(**kwargs):
        active = orchestrator_provider() if orchestrator_provider is not None else orchestrator
        if active is None:
            raise RuntimeError("GraphRAG orchestrator is not ready")
        state = await active.ainvoke(
            {"question": kwargs.get("query", ""), "top_k": kwargs.get("top_k", 10)}
        )
        if name.startswith("search."):
            source = name.split(".", 1)[1]
            return {
                "hits": [hit for hit in (state.get("hits") or []) if hit.get("source") == source]
            }
        return {
            "answer": state.get("answer", ""),
            "audit": state.get("audit") or [],
            "retrieval_trace": state.get("hits") or [],
            "tool_calls": state.get("tool_calls") or [],
        }

    _handler.__name__ = name.replace(".", "_")
    _handler.__doc__ = spec.description
    mcp.tool(name=name, description=spec.description)(_handler)


def _stub_app():
    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 503, "headers": []})
        await send({"type": "http.response.body", "body": b"mcp sdk not installed"})

    return app


class _ApiKeyASGI:
    def __init__(self, app: Any, api_key: str) -> None:
        self._app = app
        self._api_key = api_key

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = {key.lower(): value for key, value in scope.get("headers", [])}
            supplied = headers.get(b"x-api-key", b"").decode("utf-8", errors="ignore")
            if not secrets.compare_digest(supplied, self._api_key):
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"detail":"invalid API key"}',
                    }
                )
                return
        await self._app(scope, receive, send)


def mount_mcp(
    app: Any,
    *,
    orchestrator_provider: Callable[[], Any | None],
    api_key: str | None = None,
    path: str = "/v1/mcp",
) -> None:
    """Mount the MCP application with the same runtime orchestrator as HTTP."""
    mcp_app = build_mcp_app(orchestrator_provider=orchestrator_provider)
    if api_key:
        mcp_app = _ApiKeyASGI(mcp_app, api_key)
    app.mount(path, mcp_app, name="mcp")
