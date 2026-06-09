"""Generator node — LiteLLM + Instructor structured answer with citations."""

from __future__ import annotations

import logging
from typing import Any

from .._utils import digest, now_iso
from ..state import Citation, GraphState

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "你是 GraphRAG Copilot，一个严谨的知识问答助手。\n\n"
    "**核心规则（必须严格遵守）：**\n"
    "1. **只基于证据回答**：每个事实声明必须有 [chunk:N] 引用，N 是 1-based 索引\n"
    "2. **禁止编造**：如果证据中没有相关信息，必须明确说「根据现有信息无法回答」\n"
    "3. **禁止推断**：不要从证据中推导出未明确陈述的结论\n"
    "4. **多跳问题分步推理**：对于需要综合多个证据的问题，先列出每个证据的关键信息，再综合得出结论\n"
    "5. **引用格式**：每个关键结论后必须标注 [chunk:N]，如「系统使用 FAISS [chunk:1] 和 BM25 [chunk:2]」\n"
    "6. **不确定时拒答**：如果证据质量低或信息不足，直接说「信息不足，无法准确回答」\n\n"
    "**输出格式：**\n"
    "- 直接回答，不要说「根据证据」之类的开场白\n"
    "- 每个要点单独一行，便于阅读\n"
    "- 如果无法回答，只输出「根据现有信息无法回答这个问题。」"
)


def generator_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
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
            f"[chunk:{i + 1}] (来源={h.get('source')}, 相关度={score:.3f})\n{h.get('content', '')}"
        )
    evidence_block = "\n\n".join(evidence_lines) or "(无证据)"

    user_prompt = f"问题：{question}\n\n可用证据：\n{evidence_block}\n\n请严格基于上述证据回答，每个结论标注 [chunk:N] 引用。"

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
