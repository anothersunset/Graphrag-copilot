"""Fallback node — low-confidence response with explicit caveat."""

from __future__ import annotations

from typing import Any

from .._utils import digest, now_iso
from ..state import GraphState


def _is_cjk_question(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def fallback_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    question = state["question"]
    score = float(state.get("crag_score", 0.0))
    n_hits = len(state.get("fused_hits", []))

    # Answer in the user's language — a refusal the downstream refusal
    # detector can't recognize is worse than no refusal at all.
    if _is_cjk_question(question):
        msg = (
            "根据现有证据无法可靠回答这个问题"
            f"（crag_score={score:.2f}，evidence_hits={n_hits}）。"
            "请尝试换一种问法，或补充相关文档。"
        )
    else:
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
        # Emit the provenance keys even on the fallback path so the state
        # contract is uniform regardless of which branch terminated — the
        # API response and eval layer can rely on them always being present.
        "cited_chunk_ids": [],
        "claims": [],
        "auditor_verdict": "warn",
        "auditor_notes": ["fallback path taken"],
        "audit": [audit],
    }
