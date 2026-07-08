"""Planner node — analyse the question, choose tools, set retrieval plan.

v3.2: the planner classifies the query into a retrieval **mode** before
fanning out, following the local/global split from Microsoft GraphRAG
(Edge et al., 2024) and the dual-level keyword routing of LightRAG:

* ``local``  — entity-anchored factual questions. Best served by chunk
  retrieval (vector + bm25) plus entity-seeded KG traversal / PPR.
* ``global`` — corpus-level sensemaking questions ("总结", "主要主题",
  "overall", "compare across ..."). Chunk-level retrieval structurally
  cannot answer these; they are routed to community-report retrieval
  (``retrieve_kg_global``) over the Leiden/Louvain community summaries.
* ``hybrid`` — aggregation cues AND concrete entities; both routes fire.

An injected ``planner_client`` (LLM) can override the heuristic: it must
expose ``classify(question) -> {"mode": ..., "entities": [...]}``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .._utils import digest, now_iso
from ..state import GraphState

logger = logging.getLogger(__name__)

# Aggregation / sensemaking cues → global mode.
_GLOBAL_CUES_ZH = (
    "总结", "概述", "综述", "整体", "全局", "主要主题", "主要内容", "有哪些主题",
    "共同点", "趋势", "全部文档", "所有文档", "知识库里", "整个知识库", "汇总",
)
_GLOBAL_CUES_EN = (
    "summarize", "summary", "overview", "overall", "main themes", "key themes",
    "across all", "across the", "in general", "high level", "high-level",
    "what topics", "main topics", "landscape", "compare all",
)

# Latin tokens with inner uppercase / digits look like named tech entities
# (Neo4j, GraphRAG, BM25, GPT-4) — a cheap language-independent NER proxy.
_LATIN_ENTITY_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_\-]*[A-Z0-9][A-Za-z0-9_\-]*\b")

QueryMode = str  # "local" | "global" | "hybrid"


def _has_entity_anchor(question: str) -> bool:
    # Inner-caps / digit-bearing Latin tokens (Neo4j, GraphRAG, GPT-4).
    if _LATIN_ENTITY_RE.search(question):
        return True
    # Chinese proper nouns only. NOTE: jieba's ``eng`` flag tags *every*
    # ASCII word, so it must NOT be treated as an entity signal — that
    # would make every English sentence look entity-anchored.
    try:
        import jieba.posseg as pseg

        return any(
            flag in ("nr", "ns", "nt", "nz") and len(word) >= 2
            for word, flag in pseg.cut(question)
        )
    except ImportError:
        return False


def classify_query_mode(question: str) -> QueryMode:
    """Cheap deterministic local/global/hybrid classifier."""
    q_lower = question.lower()
    has_global_cue = any(c in question for c in _GLOBAL_CUES_ZH) or any(
        c in q_lower for c in _GLOBAL_CUES_EN
    )
    if not has_global_cue:
        return "local"
    # Global cue present — if the question also anchors on a concrete
    # entity ("总结一下 Neo4j 相关的内容"), keep the local routes alive too.
    return "hybrid" if _has_entity_anchor(question) else "global"


def planner_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Plan retrieval strategy for the question."""
    cfg = config or {}
    question = state["question"]
    logger.info("planner: question=%r", question)

    mode: QueryMode
    planner_client = cfg.get("planner_client")
    if planner_client is not None:
        try:
            result = planner_client.classify(question)
            mode = result.get("mode", "local")
        except Exception:
            logger.exception("planner: LLM classify failed; using heuristic")
            mode = classify_query_mode(question)
    else:
        mode = classify_query_mode(question)

    plan = {
        "intent": "sensemaking" if mode == "global" else "factual_qa",
        "mode": mode,
        "needs_decomposition": False,
        "estimated_difficulty": "medium",
        "language": "auto",
    }

    enable_kg = cfg.get("enable_kg", True)
    enable_global = cfg.get("enable_global_search", True) and enable_kg

    tools: list[str] = []
    if mode in ("local", "hybrid"):
        tools.extend(["retrieve_vector", "retrieve_bm25"])
        if enable_kg:
            tools.append("retrieve_kg")
    if mode in ("global", "hybrid") and enable_global:
        tools.append("retrieve_kg_global")
    if not tools:
        # Global mode with KG/global disabled — fall back to chunk routes
        # rather than retrieving nothing at all.
        tools.extend(["retrieve_vector", "retrieve_bm25"])
    if cfg.get("enable_web_search", False):
        tools.append("retrieve_web")

    audit_entry = {
        "node": "planner",
        "decision": f"fanout:{mode}",
        "rationale": f"mode={mode}; selected {len(tools)} retrievers for intent={plan['intent']}",
        "inputs_digest": digest(question),
        "outputs_digest": digest({"plan": plan, "tools": tools}),
        "timestamp": now_iso(),
    }

    return {
        "plan": plan,
        "tools_to_call": tools,
        "audit": [audit_entry],
    }
