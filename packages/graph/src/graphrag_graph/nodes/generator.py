"""Generator node — LiteLLM + Instructor structured answer with citations."""
from __future__ import annotations

import logging
from typing import Any

from .._utils import digest, now_iso
from ..state import Citation, GraphState

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are GraphRAG Copilot, a careful retrieval-augmented assistant. "
    "Answer the user's question using ONLY the supplied evidence chunks. "
    "Cite each factual claim with [chunk:N] where N is the 1-based chunk "
    "index. If the evidence is insufficient, say so explicitly — do not "
    "invent citations."
)


def generator_node(
    state: GraphState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    cfg = config or {}
    llm = cfg.get("llm_client")
    model = cfg.get("generator_model", "openai/gpt-4o-mini")
    timeout_s = float(cfg.get("llm_timeout_s", 30.0))

    question = state["question"]
    fused = state.get("fused_hits", [])

    evidence_lines = []
    for i, h in enumerate(fused):
        score = h.get("rerank_score") or h.get("score") or 0.0
        evidence_lines.append(
            f"[chunk:{i + 1}] (source={h.get('source')}, score={score:.3f})\n"
            f"{h.get('content', '')}"
        )
    evidence_block = "\n\n".join(evidence_lines) or "(no evidence)"

    user_prompt = f"Question:\n{question}\n\nEvidence:\n{evidence_block}"

    if llm is None:
        answer = (
            f"[skeleton] Based on {len(fused)} evidence chunks, the answer to "
            f"{question!r} would be synthesized here."
        )
    else:
        result = llm.complete(
            model=model,
            system=SYSTEM_PROMPT,
            user=user_prompt,
            timeout_s=timeout_s,
        )
        if isinstance(result, str):
            answer = result
        else:
            # Instructor structured output — expect .answer field
            answer = getattr(result, "answer", str(result))

    citations: list[Citation] = [
        {
            "chunk_id": str(h.get("chunk_id") or i + 1),
            "span": (h.get("content") or "")[:120],
            "confidence": float(h.get("rerank_score") or h.get("score", 0.0)),
        }
        for i, h in enumerate(fused)
    ]

    audit = {
        "node": "generator",
        "decision": "generated",
        "rationale": f"answer_len={len(answer)} citations={len(citations)}",
        "inputs_digest": digest({"q": question, "n_evidence": len(fused)}),
        "outputs_digest": digest(answer[:200]),
        "timestamp": now_iso(),
    }

    return {
        "answer": answer,
        "citations": citations,
        "audit": [audit],
    }
