"""ToolSpec registry shape."""
from __future__ import annotations

from graphrag_api.mcp.tools import TOOL_REGISTRY


def test_registry_exposes_four_routes_plus_orchestrator():
    names = set(TOOL_REGISTRY.keys())
    assert names == {
        "search.vector",
        "search.bm25",
        "search.kg",
        "search.web",
        "orchestrate.ask",
    }


def test_retrieval_tools_share_input_schema():
    schemas = [
        TOOL_REGISTRY[n].input_schema
        for n in ("search.vector", "search.bm25", "search.kg", "search.web")
    ]
    assert all(s == schemas[0] for s in schemas[1:])
    assert "query" in schemas[0]["properties"]
    assert schemas[0]["required"] == ["query"]


def test_tool_spec_to_mcp_marks_read_only():
    spec = TOOL_REGISTRY["search.vector"]
    mcp_dict = spec.to_mcp()
    assert mcp_dict["annotations"]["readOnlyHint"] is True
    assert mcp_dict["name"] == "search.vector"
    assert "inputSchema" in mcp_dict and "outputSchema" in mcp_dict
