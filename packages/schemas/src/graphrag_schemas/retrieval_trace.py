"""Retrieval trace and CRAG decision schemas.

``CRAGBranch``/``CRAGDecision`` are defined once in ``graphrag_schemas.crag``
and re-exported here for import compatibility.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .crag import CRAGBranch, CRAGDecision

__all__ = [
    "CRAGBranch",
    "CRAGDecision",
    "RetrievalStep",
    "RetrievalTrace",
    "RetrieverKind",
    "ToolKind",
    "ToolSpec",
]


class RetrieverKind(StrEnum):
    """Supported retriever backends."""

    VECTOR = "vector"
    BM25 = "bm25"
    KG = "kg"
    WEB = "web"


class ToolKind(StrEnum):
    """Categories of tool invocations."""

    RETRIEVAL = "retrieval"
    RERANK = "rerank"
    GENERATION = "generation"
    AUDIT = "audit"


class RetrievalStep(BaseModel):
    """A single retriever invocation within a trace."""

    model_config = {"frozen": True}

    parent_trace_id: UUID
    retriever: RetrieverKind
    query: str
    top_k: int
    started_at: datetime
    finished_at: datetime
    latency_ms: float
    hit_count: int = 0
    error: str | None = None


class RetrievalTrace(BaseModel):
    """Full trace of a retrieval pass across all retrievers."""

    trace_id: UUID
    session_id: UUID
    user_query: str
    started_at: datetime
    finished_at: datetime
    total_latency_ms: float
    steps: list[RetrievalStep] = Field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """All steps must belong to this trace."""
        return all(s.parent_trace_id == self.trace_id for s in self.steps)

    def by_retriever(self, kind: RetrieverKind) -> list[RetrievalStep]:
        """Return steps filtered by retriever kind."""
        return [s for s in self.steps if s.retriever is kind]


_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class ToolSpec(BaseModel):
    """Declarative spec for a tool exposed via MCP or internal registry."""

    model_config = {"frozen": True}

    name: str
    kind: ToolKind
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _name_must_be_snake_case(cls, v: str) -> str:
        if not _SNAKE_CASE_RE.match(v):
            raise ValueError(f"Tool name {v!r} must be lowercase snake_case")
        return v
