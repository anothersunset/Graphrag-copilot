"""Retrieval trace and CRAG decision schemas."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RetrieverKind(str, Enum):
    """Supported retriever backends."""

    VECTOR = "vector"
    BM25 = "bm25"
    KG = "kg"
    WEB = "web"


class ToolKind(str, Enum):
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


class CRAGBranch(str, Enum):
    """CRAG routing branches."""

    USE = "use"
    REWRITE = "rewrite"
    FALLBACK = "fallback"


class CRAGDecision(BaseModel):
    """A CRAG routing decision with provenance."""

    model_config = {"frozen": True}

    parent_trace_id: UUID
    branch: CRAGBranch
    confidence_score: float
    reasoning: str
    rewrite_count: int = 0

    @classmethod
    def from_score(
        cls,
        parent_trace_id: UUID,
        confidence_score: float,
        reasoning: str,
        rewrite_count: int = 0,
        use_threshold: float = 0.7,
        rewrite_threshold: float = 0.3,
        max_rewrites: int = 2,
    ) -> CRAGDecision:
        """Derive branch from score and rewrite count."""
        if rewrite_count >= max_rewrites:
            branch = CRAGBranch.FALLBACK
        elif confidence_score >= use_threshold:
            branch = CRAGBranch.USE
        elif confidence_score >= rewrite_threshold:
            branch = CRAGBranch.REWRITE
        else:
            branch = CRAGBranch.FALLBACK
        return cls(
            parent_trace_id=parent_trace_id,
            branch=branch,
            confidence_score=confidence_score,
            reasoning=reasoning,
            rewrite_count=rewrite_count,
        )


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
