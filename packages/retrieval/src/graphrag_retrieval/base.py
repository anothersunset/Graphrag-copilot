"""Retrieval base types + Reciprocal Rank Fusion."""
from __future__ import annotations

from typing import Any, Iterable, Literal, Protocol, Sequence, TypedDict, runtime_checkable

Source = Literal["vector", "bm25", "kg", "web"]


class RetrievalHit(TypedDict, total=False):
    """A single retrieved chunk.

    v3.2: ``path`` and ``visited_node_ids`` are populated by the KG
    retriever (and ignored by other routes) so EvidencePack can preserve
    multi-hop structure end-to-end.
    """

    chunk_id: str
    source: Source
    score: float
    rerank_score: float | None
    content: str
    metadata: dict[str, Any]
    # v3.2 extensions — KG only
    path: dict[str, Any] | None
    visited_node_ids: list[str]


@runtime_checkable
class AsyncRetriever(Protocol):
    """Async single-route retriever."""

    name: Source

    async def aretrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        ...


def rrf_fuse(
    route_results: Sequence[Sequence[RetrievalHit]],
    *,
    k: int = 60,
    chunk_id_key: str = "chunk_id",
) -> list[RetrievalHit]:
    """Reciprocal Rank Fusion across multiple ranked lists.

    Preserves v3.2 ``path`` and ``visited_node_ids`` from KG hits when
    present.
    """
    if not route_results:
        return []

    rrf_scores: dict[str, float] = {}
    best_seen: dict[str, RetrievalHit] = {}

    for route in route_results:
        for rank, hit in enumerate(route, start=1):
            key = hit.get(chunk_id_key) or _content_key(hit.get("content", ""))
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank)
            prior = best_seen.get(key)
            if prior is None or (hit.get("score", 0.0) > prior.get("score", 0.0)):
                best_seen[key] = hit

    fused: list[RetrievalHit] = []
    for key, rrf_score in rrf_scores.items():
        h = dict(best_seen[key])
        h["score"] = rrf_score
        fused.append(h)

    fused.sort(key=lambda h: h.get("score", 0.0), reverse=True)
    return fused


def _content_key(content: str, *, prefix_len: int = 80) -> str:
    import hashlib

    return "sha256:" + hashlib.sha256(content[:prefix_len].encode()).hexdigest()[:16]


def batched(items: Iterable, *, n: int):
    """Yield successive batches of ``n`` items."""
    batch: list = []
    for item in items:
        batch.append(item)
        if len(batch) == n:
            yield batch
            batch = []
    if batch:
        yield batch
