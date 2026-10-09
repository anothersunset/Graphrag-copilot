"""CRAG (Corrective RAG) decision schema — single source of truth.

``CRAGBranch``/``CRAGDecision`` previously lived here AND in
``retrieval_trace.py`` with diverging fields and thresholds; they are now
defined only here and re-exported from ``retrieval_trace`` for import
compatibility.

Branch derivation is caller-parameterized (``from_score``): the schema
defaults to the original v3.1 spec values (0.7/0.3, max 2 rewrites),
while the runtime scorer (``graphrag_graph.crag.CragScorer``) passes the
benchmark-tuned 0.5/0.2. Rewrite-budget exhaustion always wins — a query
that already burned its rewrites falls back regardless of score.

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
    """One CRAG evaluator decision, with provenance."""

    model_config = ConfigDict(frozen=True)

    decision_id: UUID = Field(default_factory=uuid4)
    parent_trace_id: UUID
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence_score: float = Field(ge=0.0, le=1.0)
    branch: CRAGBranch
    rewrite_count: int = Field(default=0, ge=0)
    reasoning: str = Field(min_length=10, max_length=2000)
    evaluated_doc_ids: list[str] = Field(default_factory=list)

    @classmethod
    def from_score(
        cls,
        parent_trace_id: UUID,
        *,
        confidence_score: float,
        reasoning: str,
        rewrite_count: int = 0,
        use_threshold: float = 0.7,
        rewrite_threshold: float = 0.3,
        max_rewrites: int = 2,
        evaluated_doc_ids: list[str] | None = None,
    ) -> CRAGDecision:
        """Derive the branch from score, thresholds and rewrite budget."""
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
            confidence_score=confidence_score,
            branch=branch,
            rewrite_count=rewrite_count,
            reasoning=reasoning,
            evaluated_doc_ids=evaluated_doc_ids or [],
        )
