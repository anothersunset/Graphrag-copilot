"""Reciprocal Rank Fusion correctness."""
from __future__ import annotations

from graphrag_retrieval.base import rrf_fuse


def _hit(chunk_id, score=0.5, source="vector", content=""):
    return {
        "chunk_id": chunk_id,
        "source": source,
        "score": score,
        "content": content or chunk_id,
        "metadata": {},
    }


def test_rrf_single_list_preserves_order():
    route = [_hit("a"), _hit("b"), _hit("c")]
    fused = rrf_fuse([route], k=60)
    assert [h["chunk_id"] for h in fused] == ["a", "b", "c"]


def test_rrf_boosts_documents_appearing_in_multiple_lists():
    list_a = [_hit("x"), _hit("y"), _hit("z")]
    list_b = [_hit("y"), _hit("x"), _hit("w")]
    fused = rrf_fuse([list_a, list_b], k=60)
    ids = [h["chunk_id"] for h in fused]
    # x and y appear in both lists → they should rank above w and z
    assert ids.index("x") < ids.index("z")
    assert ids.index("y") < ids.index("w")


def test_rrf_handles_empty_routes():
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []


def test_rrf_dedup_by_chunk_id():
    route_a = [_hit("a", score=0.9), _hit("b", score=0.5)]
    route_b = [_hit("a", score=0.4)]
    fused = rrf_fuse([route_a, route_b], k=60)
    ids = [h["chunk_id"] for h in fused]
    assert ids.count("a") == 1
    # a appears in both, b only in one → a outranks b
    assert ids.index("a") < ids.index("b")


def test_rrf_dedup_by_content_when_no_chunk_id():
    # Some web routes don't carry chunk_id; fusion must still dedup by content.
    a = {"source": "web", "score": 0.9, "content": "Paris is the capital of France."}
    b = {"source": "web", "score": 0.4, "content": "Paris is the capital of France."}
    fused = rrf_fuse([[a], [b]])
    assert len(fused) == 1
