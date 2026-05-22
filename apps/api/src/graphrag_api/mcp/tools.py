"""ToolSpec definitions for the four retrieval routes + the orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    """Self-describing tool used by the MCP server.

    Mirrors the ``ToolSpec`` schema in packages/schemas so external MCP
    clients (Claude Desktop, Cursor) see the exact same fields whether
    they introspect over the wire or load the schema package directly.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    side_effects: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_mcp(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "annotations": {
                "readOnlyHint": not self.side_effects,
                "idempotent": not self.side_effects,
                "openWorld": False,
            },
            "metadata": self.metadata,
        }


_RETRIEVAL_INPUT = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "top_k": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
    },
    "required": ["query"],
    "additionalProperties": False,
}

_RETRIEVAL_OUTPUT = {
    "type": "object",
    "properties": {
        "hits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "string"},
                    "source": {"type": "string"},
                    "score": {"type": "number"},
                    "rerank_score": {"type": ["number", "null"]},
                    "content": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["chunk_id", "source", "score", "content"],
            },
        }
    },
    "required": ["hits"],
}


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search.vector": ToolSpec(
        name="search.vector",
        description="Dense vector retrieval over the Qdrant collection (bge-large-zh-v1.5 embeddings).",
        input_schema=_RETRIEVAL_INPUT,
        output_schema=_RETRIEVAL_OUTPUT,
        metadata={"route": "vector"},
    ),
    "search.bm25": ToolSpec(
        name="search.bm25",
        description="Sparse BM25 retrieval with jieba tokenization over the local corpus.",
        input_schema=_RETRIEVAL_INPUT,
        output_schema=_RETRIEVAL_OUTPUT,
        metadata={"route": "bm25"},
    ),
    "search.kg": ToolSpec(
        name="search.kg",
        description="Knowledge graph 1-hop Cypher retrieval over Neo4j.",
        input_schema=_RETRIEVAL_INPUT,
        output_schema=_RETRIEVAL_OUTPUT,
        metadata={"route": "kg"},
    ),
    "search.web": ToolSpec(
        name="search.web",
        description="Public web search via the configured adapter (Tavily by default; disabled if no key).",
        input_schema=_RETRIEVAL_INPUT,
        output_schema=_RETRIEVAL_OUTPUT,
        metadata={"route": "web"},
    ),
    "orchestrate.ask": ToolSpec(
        name="orchestrate.ask",
        description="Run the full 7-node LangGraph pipeline and return answer + audit + retrieval trace.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "audit": {"type": "array", "items": {"type": "object"}},
                "retrieval_trace": {"type": "array", "items": {"type": "object"}},
                "tool_calls": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["answer", "audit", "retrieval_trace", "tool_calls"],
        },
        metadata={"node_count": 7},
    ),
}
