"""Retriever node — fan-out to all selected retrievers and merge hits.

W2 skeleton: synchronous fan-out. W3 switches to ``asyncio.gather`` over the
four-route retrievers and adds BGE-Reranker-v2-m3 inline.
"""
from __future__ import annotations

import logging
from typing import Any

from .._utils import digest, merge_hits, now_iso
from ..state import GraphState, RetrievalHit

logger = logging.getLogger(__name__)


def retriever_node(
    state: GraphState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    cfg = config or {}
    question = state["question"]
    rewrites = state.get("query_rewrites", [])
    query = rewrites[-1] if rewrites else question

    tools = state.get("tools_to_call", [])
    retrievers = cfg.get("retrievers", {})
    reranker = cfg.get("reranker")
    top_k = int(cfg.get("max_hits", 20))
    top_k_rerank = int(cfg.get("top_k_after_rerank", 5))

    all_hits: list[RetrievalHit] = []
    tool_calls: list[dict[str, Any]] = []

    for tool in tools:
        name = tool.replace("retrieve_", "")
        r = retrievers.get(name)
        if r is None:
            logger.debug(
                "retriever: no implementation registered for %s; skipping", name
            )
            continue
        started = now_iso()
        try:
            hits = r.retrieve(query, top_k=top_k)
            tool_calls.append(
                {
                    "tool": tool,
                    "args": {"query": query, "top_k": top_k},
                    "started_at": started,
                    "ended_at": now_iso(),
                    "latency_ms": 0,  # filled by observability layer in W5
                    "ok": True,
                    "error": None,
                }
            )
            all_hits.extend(hits)
        except Exception as exc:  # noqa: BLE001 — bubble into trace
            logger.exception("retriever: %s failed", name)
            tool_calls.append(
                {
                    "tool": tool,
                    "args": {"query": query, "top_k": top_k},
                    "started_at": started,
                    "ended_at": now_iso(),
                    "latency_ms": 0,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    merged = merge_hits(all_hits)
    if reranker is not None and merged:
        fused = reranker.rerank(query, merged, top_k=top_k_rerank)
    else:
        fused = sorted(merged, key=lambda h: h.get("score", 0.0), reverse=True)[
            :top_k_rerank
        ]

    audit = {
        "node": "retriever",
        "decision": "fused" if reranker else "fused_no_rerank",
        "rationale": (
            f"called {len(tool_calls)} retrievers, "
            f"merged {len(merged)} raw → {len(fused)} fused hits"
        ),
        "inputs_digest": digest({"query": query, "tools": tools}),
        "outputs_digest": digest([h.get("chunk_id") for h in fused]),
        "timestamp": now_iso(),
    }

    return {
        "hits": all_hits,
        "fused_hits": fused,
        "tool_calls": tool_calls,
        "audit": [audit],
    }
