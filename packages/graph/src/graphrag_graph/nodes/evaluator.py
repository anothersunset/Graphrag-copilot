"""Evaluator node — wraps CragScorer."""

from __future__ import annotations

from datetime import UTC, datetime

from ..crag import CragScorer
from ..state import AuditEntry


def evaluator_node(state: dict, *, config: dict | None = None) -> dict:
    """Score the current candidate set and emit a CRAG decision."""
    config = config or {}
    scorer: CragScorer = config.get("crag_scorer") or CragScorer()
    hits = state.get("fused_hits") or state.get("hits") or []
    result = scorer.score(state.get("query", ""), hits)

    audit = AuditEntry(
        node="evaluator",
        timestamp=datetime.now(UTC).isoformat(),
        summary=f"CRAG decision={result.decision} score={result.score:.3f}",
        detail={
            "score": result.score,
            "relevance": result.relevance,
            "coverage": result.coverage,
            **result.detail,
        },
    )
    return {
        "crag_score": result.score,
        "crag_decision": result.decision,
        "audit": [audit],
    }
