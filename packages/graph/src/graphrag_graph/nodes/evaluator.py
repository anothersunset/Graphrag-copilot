"""Evaluator node — wraps CragScorer."""

from __future__ import annotations

from datetime import UTC, datetime

from ..crag import CragScorer


def evaluator_node(state: dict, *, config: dict | None = None) -> dict:
    """Score the current candidate set and emit a CRAG decision."""
    config = config or {}
    scorer: CragScorer = config.get("crag_scorer") or CragScorer()
    hits = state.get("fused_hits") or state.get("hits") or []
    # state key is ``question`` (see state.py); ``query`` kept as a
    # backwards-compatible fallback in case a caller mutated state.
    query = state.get("question", "") or state.get("query", "")
    result = scorer.score(query, hits)

    audit = {
        "node": "evaluator",
        "decision": result.decision,
        "rationale": (
            f"CRAG score={result.score:.3f} "
            f"relevance={result.relevance:.3f} coverage={result.coverage:.3f}"
        ),
        "inputs_digest": "",
        "outputs_digest": "",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return {
        "crag_score": result.score,
        "crag_decision": result.decision,
        "audit": [audit],
    }
