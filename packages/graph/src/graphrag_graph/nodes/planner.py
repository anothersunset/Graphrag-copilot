"""Planner node — analyse the question, choose tools, set retrieval plan."""

from __future__ import annotations

import json
import logging
from typing import Any

from .._utils import digest, now_iso
from ..state import GraphState

logger = logging.getLogger(__name__)

PLANNER_PROMPT = (
    "你是检索策略规划专家。分析用户问题，输出 JSON 决定检索策略。\n\n"
    "输出格式：\n"
    '{"intent": "factual|relational|multihop|compare|summarize", '
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
    "- 如果问题涉及多个实体或需要图谱关系，needs_kg=true"
)


def _call_llm(llm: Any, question: str) -> dict:
    """调用 LLM 分析问题类型。"""
    try:
        result = llm.complete(
            model="",
            system=PLANNER_PROMPT,
            user=f"问题：{question}",
            timeout_s=10.0,
        )
        # 解析 JSON
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
        return json.loads(clean)
    except Exception as e:
        logger.warning("planner LLM failed: %s", e)
        return {}


def planner_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Plan retrieval strategy for the question.

    使用 LLM 分析问题类型，动态选择检索策略。
    """
    cfg = config or {}
    question = state["question"]
    llm = cfg.get("llm_client")
    logger.info("planner: question=%r", question)

    # LLM 分析问题类型
    if llm is not None:
        analysis = _call_llm(llm, question)
    else:
        analysis = {}

    intent = analysis.get("intent", "factual")
    difficulty = analysis.get("difficulty", "medium")
    entities = analysis.get("entities", [])
    needs_kg = analysis.get("needs_kg", cfg.get("enable_kg", True))

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

    # multihop 问题增加检索深度
    if intent == "multihop" and difficulty == "hard":
        plan["extra_retrieval"] = True

    audit_entry = {
        "node": "planner",
        "decision": "fanout",
        "rationale": (
            f"intent={intent} difficulty={difficulty} "
            f"entities={entities} needs_kg={needs_kg} "
            f"selected {len(tools)} retrievers"
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
