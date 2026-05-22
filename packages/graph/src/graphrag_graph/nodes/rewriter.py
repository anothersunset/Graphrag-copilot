"""Rewriter node — rewrite the query and increment the rewrite counter."""

from __future__ import annotations

import logging
from typing import Any

from .._utils import digest, now_iso
from ..state import GraphState

logger = logging.getLogger(__name__)


def rewriter_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or {}
    rewriter = cfg.get("query_rewriter")

    question = state["question"]
    prior = list(state.get("query_rewrites", []))
    iteration = int(state.get("rewrite_iteration", 0)) + 1

    if rewriter is not None:
        new_query = rewriter.rewrite(question, prior_rewrites=prior)
    else:
        # Trivial fallback rewrite: append a clarifying suffix
        new_query = (prior[-1] if prior else question) + f" (rewrite {iteration})"

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
