"""RetrievalTrace exporter — turns hits + fusion + citations into a flat
row-per-hit trace that the frontend renders as a graph.

v3.2: rows now carry the multi-hop ``graph_path`` and the per-query
``visited_node_count`` so the frontend can draw KG edges, not just chunk
dots.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Sequence


@dataclass
class RetrievalTraceEntry:
    chunk_id: str
    source: str
    raw_rank: int | None
    raw_score: float | None
    fused_rank: int | None
    fused_score: float | None
    rerank_score: float | None
    cited: bool
    metadata: dict[str, Any]
    # v3.2: graph-side payload
    graph_path: dict[str, Any] | None = None
    visited_node_count: int = 0
    rewritten_query: str | None = None
    metadata_extra: dict[str, Any] = field(default_factory=dict)


class RetrievalTraceExporter:
    """Build the per-hit trace from graph state."""

    def export(
        self,
        *,
        hits: Sequence[dict],
        fused: Sequence[dict],
        cited_ids: Sequence[str],
        query_history: Sequence[str] | None = None,
    ) -> list[dict]:
        cited_set = set(cited_ids)

        raw_ranks: dict[tuple[str, str], tuple[int, float]] = {}
        per_hit_path: dict[tuple[str, str], dict] = {}
        visited_total: set[str] = set()

        for i, hit in enumerate(hits):
            key = (hit.get("source", ""), hit.get("chunk_id", ""))
            raw_ranks.setdefault(key, (i + 1, float(hit.get("score", 0.0))))
            if hit.get("path"):
                per_hit_path[key] = hit["path"]
            for nid in hit.get("visited_node_ids") or []:
                visited_total.add(nid)

        fused_index: dict[str, tuple[int, dict]] = {}
        for i, hit in enumerate(fused):
            fused_index[hit.get("chunk_id", "")] = (i + 1, hit)

        out: list[RetrievalTraceEntry] = []
        seen_keys: set[tuple[str, str]] = set()
        rewrite_history = list(query_history or [])
        latest_rewrite = rewrite_history[-1] if rewrite_history else None

        for hit in hits:
            source = hit.get("source", "")
            chunk_id = hit.get("chunk_id", "")
            key = (source, chunk_id)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            raw_rank, raw_score = raw_ranks[key]
            fused_rank, fused_hit = fused_index.get(chunk_id, (None, {}))
            out.append(
                RetrievalTraceEntry(
                    chunk_id=chunk_id,
                    source=source,
                    raw_rank=raw_rank,
                    raw_score=raw_score,
                    fused_rank=fused_rank,
                    fused_score=float(fused_hit.get("score", 0.0)) if fused_hit else None,
                    rerank_score=fused_hit.get("rerank_score") if fused_hit else None,
                    cited=chunk_id in cited_set,
                    metadata=dict(hit.get("metadata") or {}),
                    graph_path=per_hit_path.get(key),
                    visited_node_count=len(visited_total) if source == "kg" else 0,
                    rewritten_query=latest_rewrite,
                )
            )

        out.sort(
            key=lambda e: (
                0 if e.cited else 1,
                e.fused_rank if e.fused_rank is not None else 9999,
                e.raw_rank if e.raw_rank is not None else 9999,
            )
        )
        return [asdict(e) for e in out]
