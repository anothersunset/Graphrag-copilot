"""Planner node — analyse the question, choose tools, set retrieval plan.

v3.3: Heuristic-first planner. Uses keyword rules for fast classification,
only falls back to LLM when heuristic confidence is low.
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

# ── 关键词规则 ──
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

    # 检测 intent
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

    # 无明确信号时返回空，让 LLM fallback
    if best_score == 0:
        return {}

    # crossdoc 和 relational 可能重叠，crossdoc 优先（需要跨文档检索）
    if crossdoc_score > 0 and best != "crossdoc":
        # 如果 crossdoc 信号与其他 intent 匹配度相近，优先 crossdoc
        if crossdoc_score >= best_score - 1:
            best = "crossdoc"
            best_score = crossdoc_score

    # difficulty
    hard_score = sum(1 for kw in _HARD_KW if re.search(kw, q))
    difficulty = "hard" if hard_score > 0 or multihop_score >= 2 else ("medium" if best_score >= 2 else "easy")

    # needs_kg: multihop/relational/compare/crossdoc 通常需要图谱
    needs_kg = enable_kg and best in ("multihop", "relational", "compare", "crossdoc")

    # 提取实体（简单：大写开头的词或引号内容）
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


def planner_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Plan retrieval strategy for the question.

    优先使用规则引擎（<1ms），置信度低时 fallback 到 LLM。
    """
    cfg = config or {}
    question = state["question"]
    llm = cfg.get("llm_client")
    enable_kg = cfg.get("enable_kg", True)
    logger.info("planner: question=%r", question)

    # 先尝试规则引擎
    analysis = _heuristic_plan(question, enable_kg)

    # 规则引擎无结果时 fallback 到 LLM
    if not analysis and llm is not None:
        logger.info("planner: heuristic uncertain, falling back to LLM")
        analysis = _call_llm(llm, question)

    intent = analysis.get("intent", "factual")
    difficulty = analysis.get("difficulty", "medium")
    entities = analysis.get("entities", [])
    needs_kg = analysis.get("needs_kg", enable_kg)

    plan = {
        "intent": intent,
        "needs_decomposition": intent == "multihop",
        "estimated_difficulty": difficulty,
        "language": "auto",
        "entities": entities,
    }

    # 动态选择检索工具
    tools: list[str] = ["retrieve_vector", "retrieve_bm25"]
    if needs_kg:
        tools.append("retrieve_kg")
    if cfg.get("enable_web_search", False):
        tools.append("retrieve_web")

    # multihop/crossdoc 问题增加检索深度
    if (intent == "multihop" and difficulty == "hard") or intent == "crossdoc":
        plan["extra_retrieval"] = True

    source = analysis.get("_source", "unknown")

    audit_entry = {
        "node": "planner",
        "decision": "fanout",
        "rationale": (
            f"intent={intent} difficulty={difficulty} "
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
