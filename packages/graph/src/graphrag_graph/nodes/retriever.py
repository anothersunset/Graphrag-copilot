"""Retriever node — fan-out to all selected retrievers and merge hits.

v3.2: the node accepts BOTH retriever contracts:

* async ``aretrieve(query, *, top_k)`` — the ``packages/retrieval``
  implementations (vector / bm25 / kg / web / kg_global);
* sync ``retrieve(query, *, top_k)`` — the legacy v3.1 Protocol.

Async retrievers fan out concurrently via ``asyncio.gather``; sync ones
are pushed to a worker thread so a slow route can't serialize the rest.
The node itself stays synchronous so ``graph.invoke`` keeps working —
when LangGraph drives it from ``ainvoke`` it runs in an executor thread
where ``asyncio.run`` is safe.

It also assembles the v3.2 ``EvidencePack`` (chunks + multi-hop graph
paths + visited nodes + rerank trace) into ``state["evidence_pack"]``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from graphrag_schemas.evidence import (
    ChunkEvidence,
    EvidencePack,
    GraphNode,
    GraphPath,
    RerankTraceRow,
)

from .._utils import digest, merge_hits, now_iso
from ..state import GraphState, RetrievalHit

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run a coroutine to completion from sync code, loop or no loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # A loop is already running in this thread (rare: graph.invoke inside
    # an async frame) — run the coroutine in a fresh thread's own loop.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


async def _fan_out(
    entries: list[tuple[str, Any]], query: str, top_k: int
) -> list[tuple[str, list, str, int, str | None]]:
    """Concurrently call every retriever; never raise, always report."""

    async def _one(tool: str, r: Any):
        started = now_iso()
        t0 = time.perf_counter()
        try:
            if hasattr(r, "aretrieve"):
                hits = await r.aretrieve(query, top_k=top_k)
            else:
                hits = await asyncio.to_thread(r.retrieve, query, top_k=top_k)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return tool, list(hits), started, latency_ms, None
        except Exception as exc:
            logger.exception("retriever: %s failed", tool)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return tool, [], started, latency_ms, f"{type(exc).__name__}: {exc}"

    return await asyncio.gather(*(_one(t, r) for t, r in entries))


def retriever_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or {}
    question = state["question"]
    rewrites = state.get("query_rewrites", [])
    query = rewrites[-1] if rewrites else question

    tools = state.get("tools_to_call", [])
    retrievers = cfg.get("retrievers", {})
    reranker = cfg.get("reranker")
    top_k = int(cfg.get("max_hits", 20))
    top_k_rerank = int(cfg.get("top_k_after_rerank", 5))

    entries: list[tuple[str, Any]] = []
    for tool in tools:
        name = tool.replace("retrieve_", "")
        r = retrievers.get(name)
        if r is None:
            logger.debug("retriever: no implementation registered for %s; skipping", name)
            continue
        entries.append((tool, r))

    all_hits: list[RetrievalHit] = []
    tool_calls: list[dict[str, Any]] = []
    if entries:
        for tool, hits, started, latency_ms, error in _run_async(_fan_out(entries, query, top_k)):
            tool_calls.append(
                {
                    "tool": tool,
                    "args": {"query": query, "top_k": top_k},
                    "started_at": started,
                    "ended_at": now_iso(),
                    "latency_ms": latency_ms,
                    "ok": error is None,
                    "error": error,
                }
            )
            all_hits.extend(hits)

    merged = merge_hits(all_hits)
    if reranker is not None and merged:
        fused = reranker.rerank(query, merged, top_k=top_k_rerank)
    else:
        fused = sorted(merged, key=lambda h: h.get("score", 0.0), reverse=True)[:top_k_rerank]

    evidence_pack = _build_evidence_pack(merged=merged, fused=fused)

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
        "evidence_pack": evidence_pack,
        "tool_calls": tool_calls,
        "audit": [audit],
    }


def _build_evidence_pack(*, merged: list[RetrievalHit], fused: list[RetrievalHit]) -> dict:
    """Assemble the v3.2 EvidencePack from raw + fused hits.

    KG hits carry ``path`` / ``visited_node_ids``; everything else becomes
    a ChunkEvidence row. The rerank trace maps pre-fusion rank → post-
    fusion rank per chunk_id.
    """
    chunks: list[ChunkEvidence] = []
    paths: list[GraphPath] = []
    nodes_by_id: dict[str, GraphNode] = {}
    visited_by_id: dict[str, GraphNode] = {}

    for h in fused:
        chunks.append(
            ChunkEvidence(
                chunk_id=str(h.get("chunk_id", "")),
                source=h.get("source", "vector"),
                content=h.get("content", ""),
                score=float(h.get("score", 0.0) or 0.0),
                rerank_score=h.get("rerank_score"),
                metadata=dict(h.get("metadata", {}) or {}),
            )
        )
        path = h.get("path")
        if h.get("source") == "kg" and path:
            try:
                gp = GraphPath(
                    depth=int(path.get("depth", len(path.get("rels", [])))),
                    nodes=[GraphNode(**n) for n in path.get("nodes", [])],
                    rels=path.get("rels", []),
                    rendered=h.get("content", ""),
                )
            except Exception:
                logger.debug("evidence_pack: skipping malformed kg path", exc_info=True)
                continue
            paths.append(gp)
            for n in gp.nodes:
                nodes_by_id.setdefault(n.id, n)

    for h in merged:
        for nid in h.get("visited_node_ids", []) or []:
            visited_by_id.setdefault(str(nid), GraphNode(id=str(nid), name=str(nid)))
    for nid, node in nodes_by_id.items():
        visited_by_id.setdefault(nid, node)

    pre_rank = {h.get("chunk_id"): i + 1 for i, h in enumerate(merged)}
    rerank_trace = [
        RerankTraceRow(
            chunk_id=str(h.get("chunk_id", "")),
            pre_rerank_rank=int(pre_rank.get(h.get("chunk_id"), i + 1)),
            post_rerank_rank=i + 1,
            rerank_score=float(
                h.get("rerank_score") if h.get("rerank_score") is not None else h.get("score", 0.0)
            ),
        )
        for i, h in enumerate(fused)
    ]

    pack = EvidencePack(
        vector_chunks=chunks,
        graph_nodes=list(nodes_by_id.values()),
        graph_paths=paths,
        visited_nodes=list(visited_by_id.values()),
        rerank_trace=rerank_trace,
    )
    return pack.model_dump()
