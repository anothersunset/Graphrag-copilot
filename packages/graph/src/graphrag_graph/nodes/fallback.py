"""Fallback node — low-confidence response with explicit caveat."""

from __future__ import annotations

from typing import Any

from .._utils import digest, now_iso
from ..state import GraphState


def fallback_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    question = state["question"]
    score = float(state.get("crag_score", 0.0))
    n_hits = len(state.get("fused_hits", []))

    msg = (
        "I don't have enough confident evidence to answer this question. "
        f"(crag_score={score:.2f}, evidence_hits={n_hits}). "
        "Please rephrase or supply more sources."
    )

    audit = {
        "node": "fallback",
        "decision": "low_confidence_response",
        "rationale": f"crag_score={score:.3f} below rewrite threshold",
        "inputs_digest": digest({"q": question, "score": round(score, 4)}),
        "outputs_digest": digest(msg),
        "timestamp": now_iso(),
    }

    return {
        "answer": msg,
        "citations": [],
        "auditor_verdict": "warn",
        "auditor_notes": ["fallback path taken"],
        "audit": [audit],
    }
