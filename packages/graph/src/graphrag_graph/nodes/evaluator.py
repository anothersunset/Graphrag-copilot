"""Evaluator node — CRAG scoring on fused hits."""
from __future__ import annotations

import logging
from typing import Any

from .._utils import digest, now_iso
from ..config import CragThresholds
from ..state import GraphState

logger = logging.getLogger(__name__)


def evaluator_node(
    state: GraphState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    cfg = config or {}
    thresholds: CragThresholds = cfg.get("crag", CragThresholds())
    scorer = cfg.get("crag_scorer")

    question = state["question"]
    fused = state.get("fused_hits", [])

    if not fused:
        score = 0.0
    elif scorer is not None:
        score = float(scorer.score(question, fused))
    else:
        # Fallback heuristic: top-1 score, clipped to [0, 1]
        top_score = max(
            (h.get("rerank_score") or h.get("score", 0.0)) for h in fused
        )
        score = max(0.0, min(1.0, float(top_score)))

    decision = thresholds.decide(score)

    audit = {
        "node": "evaluator",
        "decision": decision,
        "rationale": (
            f"crag_score={score:.3f} vs thresholds use>={thresholds.use} "
            f"rewrite>={thresholds.rewrite_low}"
        ),
        "inputs_digest": digest({"q": question, "n_hits": len(fused)}),
        "outputs_digest": digest({"score": round(score, 4), "decision": decision}),
        "timestamp": now_iso(),
    }

    logger.info("evaluator: score=%.3f decision=%s", score, decision)

    return {
        "crag_score": score,
        "crag_decision": decision,
        "audit": [audit],
    }
