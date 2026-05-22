"""Planner node — analyse the question, choose tools, set retrieval plan."""
from __future__ import annotations

import logging
from typing import Any

from .._utils import digest, now_iso
from ..state import GraphState

logger = logging.getLogger(__name__)


def planner_node(
    state: GraphState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Plan retrieval strategy for the question.

    W2 skeleton: deterministic fan-out plan. W7 swaps in a DSPy
    Signature ``Question → Plan`` with LiteLLM + Instructor.
    """
    cfg = config or {}
    question = state["question"]
    logger.info("planner: question=%r", question)

    plan = {
        "intent": "factual_qa",
        "needs_decomposition": False,
        "estimated_difficulty": "medium",
        "language": "auto",
    }

    tools: list[str] = ["retrieve_vector", "retrieve_bm25"]
    if cfg.get("enable_kg", True):
        tools.append("retrieve_kg")
    if cfg.get("enable_web_search", False):
        tools.append("retrieve_web")

    audit_entry = {
        "node": "planner",
        "decision": "fanout",
        "rationale": (
            f"selected {len(tools)} retrievers for intent={plan['intent']}"
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
