"""Conditional edge routers."""

from __future__ import annotations

from .state import GraphState

DEFAULT_MAX_REWRITES = 2


def route_after_evaluator(state: GraphState) -> str:
    """Route based on CRAG decision, capped by ``max_rewrites``.

    Note: the in-graph routing uses a closure that captures ``max_rewrites``
    from ``GraphConfig`` (see ``graph._gated_route``). This standalone function
    is exposed for unit testing and uses the locked default cap of 2.
    """
    decision = state.get("crag_decision", "fallback")
    iteration = int(state.get("rewrite_iteration", 0))

    if decision == "rewrite" and iteration >= DEFAULT_MAX_REWRITES:
        return "fallback"
    return decision


def route_after_auditor(state: GraphState) -> str:
    """Currently always terminal. Reserved for retry/repair routing (W7)."""
    return "end"
