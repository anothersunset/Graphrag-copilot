"""RetrievalTraceExporter shape correctness."""

from __future__ import annotations

from graphrag_api.trace.retrieval_trace import RetrievalTraceExporter

HITS = [
    {"chunk_id": "a", "source": "vector", "score": 0.9, "content": "ca", "metadata": {"page": 1}},
    {"chunk_id": "b", "source": "vector", "score": 0.5, "content": "cb", "metadata": {}},
    {"chunk_id": "a", "source": "bm25", "score": 0.7, "content": "ca", "metadata": {}},
    {"chunk_id": "c", "source": "bm25", "score": 0.4, "content": "cc", "metadata": {}},
]
FUSED = [
    {
        "chunk_id": "a",
        "source": "vector",
        "score": 0.05,
        "rerank_score": 0.92,
        "content": "ca",
        "metadata": {},
    },
    {
        "chunk_id": "b",
        "source": "vector",
        "score": 0.03,
        "rerank_score": 0.41,
        "content": "cb",
        "metadata": {},
    },
    {
        "chunk_id": "c",
        "source": "bm25",
        "score": 0.02,
        "rerank_score": 0.20,
        "content": "cc",
        "metadata": {},
    },
]


def test_trace_one_row_per_unique_route_chunk_pair():
    out = RetrievalTraceExporter().export(hits=HITS, fused=FUSED, cited_ids=["a"])
    assert len(out) == 4  # (vector,a), (vector,b), (bm25,a), (bm25,c)
    pairs = {(e["source"], e["chunk_id"]) for e in out}
    assert pairs == {("vector", "a"), ("vector", "b"), ("bm25", "a"), ("bm25", "c")}


def test_cited_entries_sort_first():
    out = RetrievalTraceExporter().export(hits=HITS, fused=FUSED, cited_ids=["a"])
    assert out[0]["chunk_id"] == "a"
    assert out[0]["cited"] is True
    # second cited row (other route for same chunk) also surfaces high
    assert out[1]["chunk_id"] == "a"


def test_rerank_score_propagates():
    out = RetrievalTraceExporter().export(hits=HITS, fused=FUSED, cited_ids=[])
    for e in out:
        if e["chunk_id"] == "a":
            assert e["rerank_score"] == 0.92
        if e["chunk_id"] == "c":
            assert e["rerank_score"] == 0.20


def test_handles_empty_inputs():
    out = RetrievalTraceExporter().export(hits=[], fused=[], cited_ids=[])
    assert out == []
