"""BGE reranker score-injection + sort correctness."""

from __future__ import annotations

from graphrag_retrieval.reranker import BGEReranker


def test_rerank_reorders_by_injected_scores():
    hits = [
        {"chunk_id": "a", "source": "vector", "score": 0.9, "content": "cats", "metadata": {}},
        {"chunk_id": "b", "source": "vector", "score": 0.5, "content": "dogs", "metadata": {}},
        {"chunk_id": "c", "source": "vector", "score": 0.3, "content": "birds", "metadata": {}},
    ]
    # injected scorer: rank c > a > b
    fake_scorer = lambda q, contents: [
        0.6 if c == "cats" else 0.2 if c == "dogs" else 0.95 for c in contents
    ]
    reranker = BGEReranker(scorer=fake_scorer)
    top = reranker.rerank("q", hits, top_k=3)
    assert [h["chunk_id"] for h in top] == ["c", "a", "b"]
    assert top[0]["rerank_score"] == 0.95


def test_rerank_topk_truncation():
    hits = [
        {
            "chunk_id": str(i),
            "content": f"doc {i}",
            "score": 0.5,
            "source": "vector",
            "metadata": {},
        }
        for i in range(10)
    ]
    reranker = BGEReranker(scorer=lambda q, contents: [float(len(c)) for c in contents])
    top = reranker.rerank("q", hits, top_k=3)
    assert len(top) == 3
    assert all("rerank_score" in h for h in top)


def test_rerank_empty_input():
    reranker = BGEReranker(scorer=lambda q, contents: [])
    assert reranker.rerank("q", [], top_k=5) == []
