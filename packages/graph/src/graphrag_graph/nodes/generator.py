"""Generator node — LiteLLM + Instructor structured answer with citations."""

from __future__ import annotations

import logging
import re
from typing import Any

from .._utils import digest, now_iso
from ..state import Citation, GraphState

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "你是 GraphRAG Copilot，一个严谨的知识问答助手。\n\n"
    "**核心规则：**\n"
    "1. **优先基于证据回答**：尽量使用下方的「可用证据」回答问题\n"
    "2. **强制引用**：每个事实声明后标注 [chunk:N]，N 是证据编号\n"
    "3. **禁止编造**：不要输出证据中完全不存在的信息\n"
    "4. **允许部分回答**：如果证据只包含部分答案，回答你能找到的部分，并说明哪些部分无法确认\n"
    "5. **多跳问题分步推理**：先列出每个证据的关键信息 [chunk:N]，再综合得出结论\n"
    "6. **跨文档综合**：当证据来自不同来源/模块时，明确标注每个来源 [chunk:N]，综合多个文档的信息给出完整答案\n"
    "7. **仅在证据完全无关时拒答**：只有当证据与问题完全无关时，才输出「根据现有信息无法回答这个问题。」\n\n"
    "**输出格式：**\n"
    "- 直接回答，不要说「根据证据」之类的开场白\n"
    "- 每个要点单独一行\n"
    "- 示例：「系统使用 FAISS [chunk:1] 和 BM25 [chunk:2] 进行混合检索。」"
)


REFUSAL_ANSWER = "根据现有信息无法回答这个问题。"


def _has_citations(answer: str) -> bool:
    """检查答案是否包含 [chunk:N] 引用."""
    return bool(re.search(r"\[chunk:\d+\]", answer))


def _is_refusal(answer: str) -> bool:
    """检查答案是否是拒答."""
    refusal_markers = ["无法回答", "信息不足", "没有找到", "无法确定", "没有相关信息"]
    return any(m in answer for m in refusal_markers)


def generator_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or {}
    llm = cfg.get("llm_client")
    model = cfg.get("generator_model", "openai/gpt-4o-mini")
    timeout_s = float(cfg.get("llm_timeout_s", 30.0))

    question = state["question"]
    fused = state.get("fused_hits", [])

    evidence_lines = []
    sources_seen = set()
    for i, h in enumerate(fused):
        score = h.get("rerank_score") or h.get("score") or 0.0
        source = h.get("source", "unknown")
        sources_seen.add(source)
        evidence_lines.append(
            f"[chunk:{i + 1}] (来源={source}, 相关度={score:.3f})\n{h.get('content', '')}"
        )
    evidence_block = "\n\n".join(evidence_lines) or "(无证据)"

    # 跨文档提示：当证据来自多个来源时，提醒 LLM 综合
    crossdoc_hint = ""
    if len(sources_seen) >= 2:
        crossdoc_hint = "\n注意：以上证据来自多个不同来源，请综合所有相关来源的信息给出完整回答。"

    user_prompt = f"问题：{question}\n\n可用证据：\n{evidence_block}{crossdoc_hint}\n\n请严格基于上述证据回答，每个结论标注 [chunk:N] 引用。"

    if llm is None:
        answer = (
            f"[skeleton] Based on {len(fused)} evidence chunks, the answer to "
            f"{question!r} would be synthesized here."
        )
    else:
        try:
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
        except Exception as e:
            logger.exception("generator: LLM call failed")
            answer = REFUSAL_ANSWER

    # ── 后验检查：短答案无引用时强制拒答，长答案仅警告 ──
    if not _is_refusal(answer) and not _has_citations(answer):
        if len(answer) < 50:
            logger.warning(
                "generator: short answer without citations, forcing refusal. answer=%s",
                answer[:200],
            )
            answer = REFUSAL_ANSWER
        else:
            logger.warning(
                "generator: answer has no [chunk:N] citations (kept). answer=%s",
                answer[:200],
            )

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
