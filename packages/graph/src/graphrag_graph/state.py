"""Shared LangGraph state for the 7-node Agentic RAG flow.

State is a ``TypedDict`` because LangGraph 0.2.x reducers operate on dict-like
state by default. Lists that should accumulate across nodes use
``Annotated[list[X], operator.add]``; scalars are replaced on each return.
"""
from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict

# ---------------------------------------------------------------------------
# Sub-types
# ---------------------------------------------------------------------------


class RetrievalHit(TypedDict, total=False):
    """A single retrieved chunk before / after rerank."""

    chunk_id: str
    source: Literal["vector", "bm25", "kg", "web"]
    score: float
    rerank_score: float | None
    content: str
    metadata: dict[str, Any]


class ToolCall(TypedDict, total=False):
    """Recorded tool invocation for the retrieval trace (W6 ToolSpec format)."""

    tool: str
    args: dict[str, Any]
    started_at: str
    ended_at: str
    latency_ms: int
    ok: bool
    error: str | None


class AuditEntry(TypedDict, total=False):
    """Per-node audit log entry (W7 auditor format)."""

    node: str
    decision: str
    rationale: str
    inputs_digest: str
    outputs_digest: str
    timestamp: str


class Citation(TypedDict, total=False):
    """Generator-emitted citation tying a span to a retrieval hit."""

    chunk_id: str
    span: str
    confidence: float


# ---------------------------------------------------------------------------
# Top-level state
# ---------------------------------------------------------------------------


CragDecision = Literal["use", "rewrite", "fallback"]
AuditorVerdict = Literal["pass", "fail", "warn"]


class GraphState(TypedDict, total=False):
    """Full LangGraph state — every field is optional at runtime.

    Reducer semantics:
      * ``hits`` / ``tool_calls`` / ``audit`` / ``query_rewrites`` accumulate
        across nodes via ``operator.add``.
      * Every other field is replaced by the latest node return value.
    """

    # --- Inputs --------------------------------------------------------
    question: str
    session_id: str
    trace_id: str

    # --- Planner outputs ----------------------------------------------
    plan: dict[str, Any]
    tools_to_call: list[str]
    query_rewrites: Annotated[list[str], add]

    # --- Retriever outputs --------------------------------------------
    hits: Annotated[list[RetrievalHit], add]
    fused_hits: list[RetrievalHit]

    # --- Evaluator outputs (CRAG) -------------------------------------
    crag_score: float
    crag_decision: CragDecision
    rewrite_iteration: int

    # --- Generator outputs --------------------------------------------
    answer: str
    citations: list[Citation]

    # --- Auditor outputs ----------------------------------------------
    auditor_verdict: AuditorVerdict
    auditor_notes: list[str]

    # --- Cross-node ----------------------------------------------------
    tool_calls: Annotated[list[ToolCall], add]
    audit: Annotated[list[AuditEntry], add]
    error: str | None


def initial_state(
    question: str, *, session_id: str = "", trace_id: str = ""
) -> GraphState:
    """Convenience constructor for the minimal valid input state."""
    import uuid

    return {
        "question": question,
        "session_id": session_id or f"sess-{uuid.uuid4().hex[:8]}",
        "trace_id": trace_id or f"trace-{uuid.uuid4().hex[:12]}",
        "rewrite_iteration": 0,
        "query_rewrites": [],
        "hits": [],
        "tool_calls": [],
        "audit": [],
    }
