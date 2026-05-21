"""ToolSpec — declarative tool registry shared by LangGraph + MCP server.

Every external capability (retrieval, search, KG query, web fetch) is
declared as a ToolSpec. The LangGraph Planner node selects tools by name,
the LangGraph Tool node dispatches via the registry (W6), and the MCP server
exposes the registry to Claude Desktop / Cursor (W6).

Invariant: ``Tool Call Necessity ∈ [0.9, 1.1]`` means the model invokes
exactly the right number of tools — not over-fetching, not under-fetching.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ToolKind(StrEnum):
    """High-level capability buckets."""

    RETRIEVAL = "retrieval"
    SEARCH = "search"
    KG_QUERY = "kg_query"
    WEB_FETCH = "web_fetch"
    LLM = "llm"


class ToolSpec(BaseModel):
    """Declarative spec for a tool the agent can invoke."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    kind: ToolKind
    description: str = Field(min_length=10, max_length=500)
    input_schema: dict[str, Any] = Field(
        description="JSON Schema for tool inputs (also rendered as MCP inputSchema).",
    )
    output_schema: dict[str, Any] = Field(
        description="JSON Schema for tool outputs.",
    )
    timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    cost_per_call_usd: float = Field(default=0.0, ge=0)
    requires_secrets: list[str] = Field(
        default_factory=list,
        description="Env var names this tool needs (e.g. ['OPENAI_API_KEY']).",
    )


class ToolCall(BaseModel):
    """Record of one tool invocation, logged via Langfuse + RetrievalTrace."""

    model_config = ConfigDict(frozen=True)

    call_id: UUID = Field(default_factory=uuid4)
    tool_name: str
    invoked_by: str = Field(description="Node name from LangGraph, e.g. 'planner'.")
    arguments: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None = None
    latency_ms: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
