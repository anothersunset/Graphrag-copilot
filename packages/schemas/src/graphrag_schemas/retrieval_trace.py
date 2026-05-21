"""RetrievalTrace — the structural backbone of every retrieval in graphrag-copilot.

Every call to any retriever (vector, BM25, KG, web) MUST emit a RetrievalStep,
and every full LangGraph run MUST emit one RetrievalTrace summarizing all steps.
This is the audit trail surfaced to the user via the React Flow visualization
(W7) and ingested by Langfuse (W5).

Invariant: ``Trace Completeness = 1.00`` means every span in the run produced
a step in this trace. Enforced in tests/test_retrieval_trace.py.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class RetrieverKind(StrEnum):
    """The four retrievers in the v3.1 hybrid stack."""

    VECTOR = "vector"  # Qdrant + Contextual Retrieval
    BM25 = "bm25"  # rank_bm25 + jieba
    KG = "kg"  # Neo4j 3-hop subgraph
    WEB = "web"  # Tavily / SerpAPI fallback (CRAG)


class RetrievalStep(BaseModel):
    """A single retrieval call from one of the four retrievers."""

    model_config = ConfigDict(frozen=True)

    step_id: UUID = Field(default_factory=uuid4)
    parent_trace_id: UUID
    retriever: RetrieverKind
    query: str
    rewritten_query: str | None = Field(
        default=None,
        description="Set when CRAG rewrites the query before this step.",
    )
    top_k: int = Field(ge=1, le=200)
    started_at: datetime
    finished_at: datetime
    latency_ms: float = Field(ge=0)
    result_ids: list[str] = Field(
        default_factory=list,
        description="Document or node IDs returned, in rank order.",
    )
    scores: list[float] = Field(
        default_factory=list,
        description="Per-result relevance scores (raw, pre-rerank).",
    )
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalTrace(BaseModel):
    """Aggregate trace for one user query → final answer."""

    model_config = ConfigDict(frozen=True)

    trace_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    user_query: str
    started_at: datetime
    finished_at: datetime
    total_latency_ms: float = Field(ge=0)
    steps: list[RetrievalStep] = Field(default_factory=list)
    final_answer: str | None = None
    answer_citations: list[str] = Field(default_factory=list)
    langfuse_trace_url: str | None = None

    @property
    def is_complete(self) -> bool:
        """Trace Completeness invariant: at least one step, all steps parented correctly.

        W5 RAGAS enforces this as part of the *Trace Completeness = 1.00* SLO.
        """
        return (
            len(self.steps) > 0
            and all(step.parent_trace_id == self.trace_id for step in self.steps)
            and self.finished_at >= self.started_at
        )

    def by_retriever(self, kind: RetrieverKind) -> list[RetrievalStep]:
        """All steps from a given retriever, preserving order."""
        return [s for s in self.steps if s.retriever == kind]
