"""Rewriter node — rewrite the query and increment the rewrite counter.

v3.2: the no-LLM fallback is a real query reformulation instead of the
old ``"(rewrite N)"`` suffix (which re-issued an identical query to the
retrievers and made the CRAG rewrite loop a no-op):

* iteration 1 — keyword condensation: strip question words / stopwords
  and keep salient terms. This trades recall for precision and plays to
  BM25's strengths.
* iteration 2+ — keyword expansion: original question + salient terms
  appended, which widens the vector-side match surface.

An injected ``query_rewriter`` (LLM-backed) always takes precedence.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .._utils import digest, now_iso
from ..state import GraphState

logger = logging.getLogger(__name__)

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


def rewriter_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or {}
    rewriter = cfg.get("query_rewriter")

    question = state["question"]
    prior = list(state.get("query_rewrites", []))
    iteration = int(state.get("rewrite_iteration", 0)) + 1

    if rewriter is not None:
        new_query = rewriter.rewrite(question, prior_rewrites=prior)
    else:
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
