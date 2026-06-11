"""Rewriter node — rewrite the query using LLM to improve retrieval."""

from __future__ import annotations

import logging
from typing import Any

from .._utils import digest, now_iso
from ..state import GraphState

logger = logging.getLogger(__name__)

REWRITER_PROMPT = (
    "你是查询改写专家。根据原始问题和之前的检索结果，改写查询以提高检索质量。\n\n"
    "规则：\n"
    "1. 保持原始问题的核心意图不变\n"
    "2. 使用更精确的关键词，避免模糊表述\n"
    "3. 如果是多跳问题，拆分为更具体的子问题\n"
    "4. 补充可能的同义词或相关术语\n"
    "5. 只输出改写后的查询，不要解释\n\n"
    "示例：\n"
    "原始：系统如何从问题理解到最终生成答案？\n"
    "改写：Agent 编排器 MultiAgentOrchestrator 调用 QueryUnderstandingAgent RetrievalAgent ReasoningAgent VerificationAgent GenerationAgent 流程\n\n"
    "原始：Neo4j 不可用时系统如何降级？\n"
    "改写：RetrievalAgent 异常处理 kg_service graph_rag_search 失败 warnings 向量检索 BM25 检索降级"
)


def _call_llm(llm: Any, question: str, prior_rewrites: list[str]) -> str | None:
    """调用 LLM 改写查询。"""
    try:
        context = ""
        if prior_rewrites:
            context = f"\n\n之前的改写尝试：{prior_rewrites[-1]}"

        result = llm.complete(
            model="",
            system=REWRITER_PROMPT,
            user=f"原始问题：{question}{context}\n\n请改写查询：",
            timeout_s=10.0,
        )
        return result.strip()
    except Exception as e:
        logger.warning("rewriter LLM failed: %s", e)
        return None


def rewriter_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rewrite the query using LLM to improve retrieval quality."""
    cfg = config or {}
    llm = cfg.get("llm_client") or cfg.get("query_rewriter")

    question = state["question"]
    prior = list(state.get("query_rewrites", []))
    iteration = int(state.get("rewrite_iteration", 0)) + 1

    # 使用 LLM 改写
    if llm is not None:
        new_query = _call_llm(llm, question, prior)
        if new_query is None:
            # LLM 失败，使用 fallback
            new_query = (prior[-1] if prior else question) + f" (rewrite {iteration})"
    else:
        # Fallback: 使用启发式改写
        base = prior[-1] if prior else question
        if iteration == 1:
            # 第一次改写：补充关键词
            new_query = f"{base} 详细说明 具体实现"
        else:
            # 第二次改写：更具体的表述
            new_query = f"{base} 完整流程 步骤"

    audit = {
        "node": "rewriter",
        "decision": "rewrote",
        "rationale": f"iteration={iteration}, new_query={new_query!r}",
        "inputs_digest": digest({"q": question, "prior": prior}),
        "outputs_digest": digest(new_query),
        "timestamp": now_iso(),
    }

    logger.info("rewriter: iteration=%d new_query=%r", iteration, new_query)

    return {
        "query_rewrites": [new_query],
        "rewrite_iteration": iteration,
        "audit": [audit],
    }
