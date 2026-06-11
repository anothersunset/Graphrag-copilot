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
    "**核心规则（违反任何一条即为失败回答）：**\n"
    "1. **只基于证据回答**：你的回答中的每一句话、每一个事实，都必须来自下方的「可用证据」\n"
    "2. **强制引用**：每个事实声明后必须标注 [chunk:N]，N 是证据编号。没有 [chunk:N] 的事实声明被视为编造\n"
    "3. **禁止编造**：绝对不允许输出证据中不存在的信息。不要用自己的知识补充\n"
    "4. **禁止推断**：不要从证据中推导出未明确陈述的结论\n"
    "5. **不确定时拒答**：如果证据中没有直接答案，只输出「根据现有信息无法回答这个问题。」\n"
    "6. **多跳问题分步推理**：先列出每个证据的关键信息 [chunk:N]，再综合得出结论\n\n"
    "**输出前自检（必须执行）：**\n"
    "- 检查回答中的每个事实声明，确保都有 [chunk:N] 标注\n"
    "- 如果发现无引用的事实，删除该声明或改为拒答\n"
    "- 宁可少答也不要编造\n\n"
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
