"""Retrieval base types + Reciprocal Rank Fusion."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal, NotRequired, Protocol, TypedDict, cast, runtime_checkable

Source = Literal["vector", "bm25", "kg", "web"]


class RetrievalHit(TypedDict):
    """A single retrieved chunk.

    v3.2: ``path`` and ``visited_node_ids`` are populated by the KG
    retriever (and ignored by other routes) so EvidencePack can preserve
    multi-hop structure end-to-end.
    """

    chunk_id: str
    source: Source
    score: float
    content: str
    metadata: dict[str, Any]
    rerank_score: NotRequired[float | None]
    # v3.2 extensions — KG only
    path: NotRequired[dict[str, Any] | None]
    visited_node_ids: NotRequired[list[str]]


@runtime_checkable
class AsyncRetriever(Protocol):
    """Async single-route retriever."""

    name: Source

    async def aretrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]: ...


def rrf_fuse(
    route_results: Sequence[Sequence[Mapping[str, Any]]],
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
                best_seen[key] = _normalise_hit(hit, chunk_id=key)

    fused: list[RetrievalHit] = []
    for key, rrf_score in rrf_scores.items():
        h = _normalise_hit(best_seen[key], chunk_id=key)
        h["score"] = rrf_score
        fused.append(h)

    fused.sort(key=lambda h: h.get("score", 0.0), reverse=True)
    return fused


def _normalise_hit(hit: Mapping[str, Any], *, chunk_id: str | None = None) -> RetrievalHit:
    """Copy an external hit while enforcing the required retrieval contract."""
    data = dict(hit)
    data.setdefault("chunk_id", chunk_id or _content_key(str(data.get("content", ""))))
    data.setdefault("source", "vector")
    data.setdefault("score", 0.0)
    data.setdefault("content", "")
    data.setdefault("metadata", {})
    return cast(RetrievalHit, data)


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
