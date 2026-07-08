"""Evaluator node — wraps CragScorer."""

from __future__ import annotations

from datetime import UTC, datetime

from ..crag import CragScorer


def evaluator_node(state: dict, *, config: dict | None = None) -> dict:
    """Score the current candidate set and emit a CRAG decision."""
    config = config or {}
    scorer: CragScorer | None = config.get("crag_scorer")
    if scorer is None:
        # Honor GraphConfig.crag thresholds + v3.2 knobs — previously they
        # were passed into node config but never reached the default scorer.
        thresholds = config.get("crag")
        kwargs: dict = {
            "spread_penalty": float(config.get("crag_spread_penalty", 0.0)),
            "min_spread": float(config.get("crag_min_spread", 0.05)),
            "judge_weight": float(config.get("crag_judge_weight", 0.5)),
            "judge": config.get("crag_judge"),
        }
        if thresholds is not None:
            kwargs["use_threshold"] = thresholds.use
            kwargs["rewrite_threshold"] = thresholds.rewrite_low
        scorer = CragScorer(**kwargs)
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
