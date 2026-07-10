"""Conditional edge routers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

DEFAULT_MAX_REWRITES = 2


def route_after_evaluator(state: Mapping[str, Any]) -> str:
    """Route based on CRAG decision, capped by ``max_rewrites``.

    Note: the in-graph routing uses a closure that captures ``max_rewrites``
    from ``GraphConfig`` (see ``graph._gated_route``). This standalone function
    is exposed for unit testing and uses the locked default cap of 2.
    """
    decision = str(state.get("crag_decision", "fallback"))
    iteration = int(state.get("rewrite_iteration", 0))

    if decision == "rewrite" and iteration >= DEFAULT_MAX_REWRITES:
        return "fallback"
    return decision


def route_after_auditor(state: Mapping[str, Any]) -> str:
    """Currently always terminal. Reserved for retry/repair routing (W7)."""
    return "end"
