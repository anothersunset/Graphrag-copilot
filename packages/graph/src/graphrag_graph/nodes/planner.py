"""Planner node — analyse the question, choose tools, set retrieval plan.

Two independent classification axes feed the retrieval plan:

* **intent/difficulty** (v3.3) — heuristic-first keyword scoring across
  factual/relational/multihop/compare/summarize/crossdoc, falling back to
  an LLM call when no rule fires. Drives ``needs_kg`` (local KG lookup)
  and ``extra_retrieval`` (deeper top_k for hard multihop/crossdoc
  questions) — validated against the 50-question benchmark (crossdoc
  accuracy +16.5pp from the keyword-rule + diversity-select combo).
* **mode** (v3.2) — local/global/hybrid classification following the
  local/global split from Microsoft GraphRAG (Edge et al., 2024) and the
  dual-level keyword routing of LightRAG:

  - ``local``  — entity-anchored factual questions → chunk retrieval
    (vector + bm25) plus entity-seeded KG traversal / PPR.
  - ``global`` — corpus-level sensemaking ("总结", "主要主题", "overall")
    that no single chunk can answer → community-report retrieval
    (``retrieve_kg_global``) over Louvain community summaries.
  - ``hybrid`` — aggregation cues AND concrete entities → both fire.

The two axes overlap conceptually (``intent="summarize"`` and
``mode="global"`` both fire on "总结") but answer different questions:
intent tunes *how hard* the chunk-level routes should work, mode decides
*whether the global community-report route joins the fan-out at all*.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .._utils import digest, now_iso
from ..state import GraphState

logger = logging.getLogger(__name__)

PLANNER_PROMPT = (
    "你是检索策略规划专家。分析用户问题，输出 JSON 决定检索策略。\n\n"
    "输出格式：\n"
    '{"intent": "factual|relational|multihop|compare|summarize|crossdoc", '
    '"difficulty": "easy|medium|hard", '
    '"entities": ["实体1", "实体2"], '
    '"needs_kg": true/false, '
    '"reasoning": "分析原因"}\n\n'
    "规则：\n"
    "- factual：单点事实查询，如「什么是 X」「X 的配置是什么」\n"
    "- relational：需要理解实体关系，如「X 如何调用 Y」「X 和 Y 的关系」\n"
    "- multihop：需要多步推理，如「从 A 到 B 的完整流程」「X 如何影响 Y 再影响 Z」\n"
    "- compare：对比分析，如「X 和 Y 的区别」\n"
    "- summarize：总结归纳，如「系统的核心架构」\n"
    "- crossdoc：需要跨多个文档/模块的证据来回答，如「系统如何支持多种格式」「X 如何与 Y 和 Z 配合」\n"
    "- 如果问题涉及多个实体或需要图谱关系，needs_kg=true"
)

# ── 关键词规则（intent/difficulty）──
_MULTIHOP_KW = ["流程", "步骤", "完整", "从.*到", "如何.*再", "影响", "调用链", "执行顺序", "pipeline"]
_RELATIONAL_KW = ["关系", "调用", "依赖", "使用", "基于", "连接", "关联", "交互"]
_COMPARE_KW = ["区别", "差异", "对比", "vs", "比较", "不同", "相同"]
_SUMMARIZE_KW = ["总结", "归纳", "概述", "整体", "核心", "主要", "架构"]
_FACTUAL_KW = ["什么是", "是什么", "配置", "参数", "地址", "端口", "版本", "定义"]
_CROSSDOC_KW = ["支持哪些", "哪些格式", "多种", "如何.*融合", "如何.*存储", "如何.*处理", "如何.*支持", "如何.*工作", "如何.*实现", "如何.*生成", "如何.*持久化"]
_HARD_KW = ["完整流程", "详细", "全面", "深入", "所有"]


def _heuristic_plan(question: str, enable_kg: bool) -> dict:
    """规则引擎快速分类，返回 analysis dict 或空 dict（置信度低时）."""
    q = question.lower()

    multihop_score = sum(1 for kw in _MULTIHOP_KW if re.search(kw, q))
    relational_score = sum(1 for kw in _RELATIONAL_KW if re.search(kw, q))
    compare_score = sum(1 for kw in _COMPARE_KW if re.search(kw, q))
    summarize_score = sum(1 for kw in _SUMMARIZE_KW if re.search(kw, q))
    factual_score = sum(1 for kw in _FACTUAL_KW if re.search(kw, q))
    crossdoc_score = sum(1 for kw in _CROSSDOC_KW if re.search(kw, q))

    scores = {
        "multihop": multihop_score,
        "relational": relational_score,
        "compare": compare_score,
        "summarize": summarize_score,
        "factual": factual_score,
        "crossdoc": crossdoc_score,
    }
    best = max(scores, key=scores.get)
    best_score = scores[best]

    if best_score == 0:
        return {}

    # crossdoc 和 relational 可能重叠，crossdoc 优先（需要跨文档检索）
    if crossdoc_score > 0 and best != "crossdoc" and crossdoc_score >= best_score - 1:
        best = "crossdoc"
        best_score = crossdoc_score

    hard_score = sum(1 for kw in _HARD_KW if re.search(kw, q))
    difficulty = "hard" if hard_score > 0 or multihop_score >= 2 else ("medium" if best_score >= 2 else "easy")

    needs_kg = enable_kg and best in ("multihop", "relational", "compare", "crossdoc")

    entities = re.findall(r'[A-Z][a-zA-Z]+(?:[A-Z][a-zA-Z]+)*', question)
    entities += re.findall(r'「([^」]+)」|"([^"]+)"', question)
    entities = list(set(e for pair in entities for e in (pair if isinstance(pair, tuple) else [pair]) if e))[:5]

    return {
        "intent": best,
        "difficulty": difficulty,
        "entities": entities,
        "needs_kg": needs_kg,
        "_source": "heuristic",
    }


def _call_llm(llm: Any, question: str) -> dict:
    """调用 LLM 分析问题类型。"""
    from ..json_compat import extract_json_object

    try:
        result = llm.complete(
            model="",
            system=PLANNER_PROMPT,
            user=f"问题：{question}",
            timeout_s=10.0,
        )
        parsed = extract_json_object(result)
        parsed["_source"] = "llm"
        return parsed
    except Exception as e:
        logger.warning("planner LLM failed: %s", e)
        return {}


# ── local/global/hybrid 查询模式（community-report 路由）──

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
    """Plan retrieval strategy for the question.

    优先使用规则引擎（<1ms），置信度低时 fallback 到 LLM；随后叠加
    local/global/hybrid 模式分类，决定是否加入 community-report 检索路由。
    """
    cfg = config or {}
    question = state["question"]
    llm = cfg.get("llm_client")
    enable_kg = cfg.get("enable_kg", True)
    logger.info("planner: question=%r", question)

    analysis = _heuristic_plan(question, enable_kg)
    if not analysis and llm is not None:
        logger.info("planner: heuristic uncertain, falling back to LLM")
        analysis = _call_llm(llm, question)

    intent = analysis.get("intent", "factual")
    difficulty = analysis.get("difficulty", "medium")
    entities = analysis.get("entities", [])
    needs_kg = analysis.get("needs_kg", enable_kg)
    source = analysis.get("_source", "unknown")

    planner_client = cfg.get("planner_client")
    if planner_client is not None:
        try:
            mode_result = planner_client.classify(question)
            mode: QueryMode = mode_result.get("mode", "local")
        except Exception:
            logger.exception("planner: LLM mode classify failed; using heuristic")
            mode = classify_query_mode(question)
    else:
        mode = classify_query_mode(question)
    # "summarize" intent is a strong corroborating signal for global mode
    # even when the cue-word list missed a paraphrase the keyword rules
    # didn't cover.
    if intent == "summarize" and mode == "local":
        mode = "hybrid" if entities else "global"

    plan = {
        "intent": intent,
        "mode": mode,
        "needs_decomposition": intent == "multihop",
        "estimated_difficulty": difficulty,
        "language": "auto",
        "entities": entities,
    }

    tools: list[str] = []
    if mode in ("local", "hybrid"):
        tools.extend(["retrieve_vector", "retrieve_bm25"])
        if needs_kg:
            tools.append("retrieve_kg")
    if mode in ("global", "hybrid") and enable_kg and cfg.get("enable_global_search", True):
        tools.append("retrieve_kg_global")
    if mode == "global" and "retrieve_kg_global" not in tools:
        # global_search disabled — fall back to chunk routes rather than
        # retrieving nothing.
        tools.extend(["retrieve_vector", "retrieve_bm25"])
    if cfg.get("enable_web_search", False):
        tools.append("retrieve_web")

    if (intent == "multihop" and difficulty == "hard") or intent == "crossdoc":
        plan["extra_retrieval"] = True

    audit_entry = {
        "node": "planner",
        "decision": f"fanout:{mode}",
        "rationale": (
            f"intent={intent} mode={mode} difficulty={difficulty} "
            f"entities={entities} needs_kg={needs_kg} "
            f"selected {len(tools)} retrievers "
            f"(source={source})"
        ),
        "inputs_digest": digest(question),
        "outputs_digest": digest({"plan": plan, "tools": tools}),
        "timestamp": now_iso(),
    }

    return {
        "plan": plan,
        "tools_to_call": tools,
        "audit": [audit_entry],
    }
