"""CRAG (Corrective RAG) decision schema.

CRAG runs after first-pass retrieval. Confidence thresholds:

- ``confidence_score >= 0.7`` → USE retrieved docs directly
- ``0.3 <= confidence_score < 0.7`` → REWRITE query and retry (cap = 2)
- ``confidence_score < 0.3`` → FALLBACK to web search

Invariant: every CRAG decision MUST be logged; AuditRecord stores it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class CRAGBranch(StrEnum):
    USE = "use"
    REWRITE = "rewrite"
    FALLBACK = "fallback"


class CRAGDecision(BaseModel):
    """One CRAG evaluator decision."""

    model_config = ConfigDict(frozen=True)

    decision_id: UUID = Field(default_factory=uuid4)
    parent_trace_id: UUID
    evaluated_at: datetime
    confidence_score: float = Field(ge=0.0, le=1.0)
    branch: CRAGBranch
    rewrite_count: int = Field(default=0, ge=0, le=2)
    reasoning: str = Field(min_length=10, max_length=2000)
    evaluated_doc_ids: list[str] = Field(default_factory=list)

    @classmethod
    def from_score(
        cls,
        *,
        parent_trace_id: UUID,
        confidence_score: float,
        reasoning: str,
        rewrite_count: int = 0,
        evaluated_doc_ids: list[str] | None = None,
    ) -> CRAGDecision:
        """Construct a decision; branch derived from score + rewrite budget."""
        if confidence_score >= 0.7:
            branch = CRAGBranch.USE
        elif confidence_score >= 0.3 and rewrite_count < 2:
            branch = CRAGBranch.REWRITE
        else:
            branch = CRAGBranch.FALLBACK
        return cls(
            parent_trace_id=parent_trace_id,
            evaluated_at=datetime.now(UTC),
            confidence_score=confidence_score,
            branch=branch,
            rewrite_count=rewrite_count,
            reasoning=reasoning,
            evaluated_doc_ids=evaluated_doc_ids or [],
        )
