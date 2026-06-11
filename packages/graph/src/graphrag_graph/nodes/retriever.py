"""Retriever node — parallel fan-out to all selected retrievers and merge hits.

v3.3: Uses ThreadPoolExecutor for parallel retrieval (vector + BM25 + KG).
v3.4: Source-diversity-aware selection for crossdoc queries.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .._utils import digest, merge_hits, now_iso
from ..state import GraphState, RetrievalHit

logger = logging.getLogger(__name__)


def _retrieve_one(tool: str, retriever: Any, query: str, top_k: int) -> tuple[str, list[RetrievalHit], dict]:
    """单个检索器调用，返回 (name, hits, tool_call_record)."""
    started = now_iso()
    t0 = time.monotonic()
    try:
        hits = retriever.retrieve(query, top_k=top_k)
        latency_ms = int((time.monotonic() - t0) * 1000)
        return tool, hits, {
            "tool": tool,
            "args": {"query": query, "top_k": top_k},
            "started_at": started,
            "ended_at": now_iso(),
            "latency_ms": latency_ms,
            "ok": True,
            "error": None,
        }
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.exception("retriever: %s failed", tool)
        return tool, [], {
            "tool": tool,
            "args": {"query": query, "top_k": top_k},
            "started_at": started,
            "ended_at": now_iso(),
            "latency_ms": latency_ms,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _get_source_doc(hit: dict) -> str:
    """从 hit 中提取来源文档标识（用于多样性分桶）."""
    meta = hit.get("metadata", {})
    # 优先用 file_name / source_file
    for key in ("file_name", "source_file", "document", "source"):
        val = meta.get(key)
        if val:
            return str(val)
    # 回退到 chunk_id 的前缀（如 "kg-xxx" → "kg"）
    cid = str(hit.get("chunk_id", ""))
    if "-" in cid:
        return cid.rsplit("-", 1)[0]
    return cid[:20] if cid else "unknown"


def _diversity_select(hits: list[dict], top_k: int) -> list[dict]:
    """来源多样性感知选择：轮询从不同文档选取 chunk，确保跨文档覆盖."""
    if not hits or top_k <= 0:
        return []

    # 按来源文档分桶
    buckets: dict[str, list[dict]] = {}
    for h in hits:
        doc = _get_source_doc(h)
        buckets.setdefault(doc, []).append(h)

    # 每个桶内按分数降序
    for bucket in buckets.values():
        bucket.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    # 轮询选取：每轮从每个桶取 1 个，直到凑满 top_k
    result = []
    bucket_keys = list(buckets.keys())
    # 按桶的最高分排序，高分桶优先
    bucket_keys.sort(key=lambda k: buckets[k][0].get("score", 0.0), reverse=True)

    indices = {k: 0 for k in bucket_keys}
    while len(result) < top_k:
        added = False
        for k in bucket_keys:
            if indices[k] < len(buckets[k]):
                result.append(buckets[k][indices[k]])
                indices[k] += 1
                added = True
                if len(result) >= top_k:
                    break
        if not added:
            break

    return result


def retriever_node(state: GraphState, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or {}
    question = state["question"]
    rewrites = state.get("query_rewrites", [])
    query = rewrites[-1] if rewrites else question

    tools = state.get("tools_to_call", [])
    retrievers = cfg.get("retrievers", {})
    reranker = cfg.get("reranker")
    base_top_k = int(cfg.get("max_hits", 20))
    top_k_rerank = int(cfg.get("top_k_after_rerank", 5))

    # multihop 问题增加检索深度
    plan = state.get("plan", {})
    if plan.get("extra_retrieval"):
        top_k = min(base_top_k * 2, 40)
    else:
        top_k = base_top_k

    all_hits: list[RetrievalHit] = []
    tool_calls: list[dict[str, Any]] = []

    # 并行调用所有检索器
    active_retrievers = {}
    for tool in tools:
        name = tool.replace("retrieve_", "")
        r = retrievers.get(name)
        if r is None:
            logger.debug("retriever: no implementation registered for %s; skipping", name)
            continue
        active_retrievers[tool] = r

    if active_retrievers:
        with ThreadPoolExecutor(max_workers=min(len(active_retrievers), 4)) as pool:
            futures = {
                pool.submit(_retrieve_one, tool, r, query, top_k): tool
                for tool, r in active_retrievers.items()
            }
            for future in as_completed(futures):
                tool_name, hits, record = future.result()
                tool_calls.append(record)
                all_hits.extend(hits)

    merged = merge_hits(all_hits)

    # crossdoc/multihop 使用更大的 top_k 和来源多样性选择
    is_crossdoc = plan.get("intent") == "crossdoc" or plan.get("extra_retrieval")
    effective_top_k = min(top_k_rerank * 2, 10) if is_crossdoc else top_k_rerank

    if reranker is not None and merged:
        fused = reranker.rerank(query, merged, top_k=effective_top_k)
    else:
        sorted_hits = sorted(merged, key=lambda h: h.get("score", 0.0), reverse=True)
        if is_crossdoc:
            fused = _diversity_select(sorted_hits, effective_top_k)
        else:
            fused = sorted_hits[:effective_top_k]

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
