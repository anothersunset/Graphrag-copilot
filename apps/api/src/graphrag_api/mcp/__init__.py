"""MCP server surface for GraphRAG Copilot."""

from .server import build_mcp_app
from .tools import TOOL_REGISTRY, ToolSpec

__all__ = ["TOOL_REGISTRY", "ToolSpec", "build_mcp_app"]
