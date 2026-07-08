"""Rewriter node — rewrite the query and increment the rewrite counter.

Rewrite strategy, in precedence order:

1. an injected ``query_rewriter`` (``.rewrite(question, *, prior_rewrites)``
   Protocol) always wins — lets callers plug in a bespoke strategy/eval
   harness without touching this node.
2. the orchestrator's ``llm_client`` — asked to reformulate the query
   with a task-specific prompt (more precise keywords, sub-question
   decomposition for multihop, synonym expansion).
3. a deterministic heuristic when neither is available, so the CRAG
   rewrite loop is never a no-op:
   * iteration 1 — keyword condensation: strip question words /
     stopwords and keep salient terms (jieba-tokenized). Trades recall
     for precision and plays to BM25's strengths.
   * iteration 2+ — keyword expansion: original question + salient
     terms appended, widening the vector-side match surface.

(The old fallback that just appended ``"(rewrite N)"`` re-issued an
identical query to the retrievers and made the rewrite loop a no-op —
both the heuristic above and the LLM path replace that.)
"""

from __future__ import annotations

import logging
import re
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
    "5. 只输出改写后的查询，不要解释"
)

_EN_STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "do", "does",
    "did", "what", "which", "who", "whom", "how", "when", "where", "why",
    "of", "in", "on", "at", "to", "for", "with", "by", "from", "as", "and",
    "but", "or", "not", "this", "that", "these", "those", "it", "its",
    "please", "explain", "describe", "tell", "me", "about", "can", "could",
    "would", "should", "will",
}
_ZH_STOP = {
    "什么", "如何", "为什么", "哪些", "哪个", "是否", "怎么", "怎样", "介绍",
    "解释", "请问", "一下", "关于", "以及", "还有", "这个", "那个", "可以",
    "能否", "有没有", "多少", "的话",
}

_TERM_RE = re.compile(r"[一-鿿]{2,}|[A-Za-z][A-Za-z0-9_\-]{2,}")


def _salient_terms(text: str) -> list[str]:
    """Salient query terms; jieba when available, regex runs otherwise."""
    terms: list[str]
    try:
        import jieba

        terms = [w.strip() for w in jieba.cut(text) if len(w.strip()) >= 2]
    except ImportError:
        terms = _TERM_RE.findall(text)
    seen: dict[str, None] = {}
    for t in terms:
        if t.lower() in _EN_STOP or t in _ZH_STOP:
            continue
        seen.setdefault(t, None)
    return list(seen)


def _heuristic_rewrite(question: str, prior: list[str], iteration: int) -> str:
    terms = _salient_terms(question)
    if not terms:
        return f"{question} ({iteration})"

    candidate = " ".join(terms) if iteration <= 1 else f"{question} {' '.join(terms)}"

    tried = {question, *prior}
    if candidate in tried:
        candidate = f"{question} {' '.join(terms[: max(1, len(terms) // 2)])}"
    if candidate in tried:
        candidate = f"{question} ({iteration})"
    return candidate


def _call_llm(llm: Any, question: str, prior_rewrites: list[str]) -> str | None:
    """调用 LLM 改写查询；失败或空结果返回 None 交给启发式兜底。"""
    try:
        context = f"\n\n之前的改写尝试：{prior_rewrites[-1]}" if prior_rewrites else ""
        result = llm.complete(
            model="",
            system=REWRITER_PROMPT,
            user=f"原始问题：{question}{context}\n\n请改写查询：",
            timeout_s=10.0,
        )
        rewritten = result.strip()
        return rewritten or None
    except Exception as e:
        logger.warning("rewriter LLM failed: %s", e)
        return None


def rewriter_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or {}
    rewriter = cfg.get("query_rewriter")
    llm = cfg.get("llm_client")

    question = state["question"]
    prior = list(state.get("query_rewrites", []))
    iteration = int(state.get("rewrite_iteration", 0)) + 1

    if rewriter is not None:
        new_query = rewriter.rewrite(question, prior_rewrites=prior)
    else:
        new_query = _call_llm(llm, question, prior) if llm is not None else None
        if new_query is None:
            new_query = _heuristic_rewrite(question, prior, iteration)

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
