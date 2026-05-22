"""Pytest fixtures: fake retrievers, fake LLM, fake auditor, fake scorer."""
from __future__ import annotations

from typing import Any, Sequence

import pytest

from graphrag_graph.state import Citation, RetrievalHit


class FakeRetriever:
    def __init__(self, name: str, hits: list[RetrievalHit]):
        self.name = name
        self._hits = hits

    def retrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        return list(self._hits)[:top_k]


class FakeReranker:
    def rerank(
        self, query: str, hits: Sequence[RetrievalHit], *, top_k: int
    ) -> list[RetrievalHit]:
        ranked = sorted(hits, key=lambda h: h.get("score", 0.0), reverse=True)[
            :top_k
        ]
        for i, h in enumerate(ranked):
            h["rerank_score"] = h.get("score", 0.0) + 0.01 * (top_k - i)
        return list(ranked)


class FakeLLM:
    def __init__(self, answer: str = "fake answer"):
        self.answer = answer
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        response_schema=None,
        timeout_s: float = 30.0,
    ):
        self.calls.append({"model": model, "system": system, "user": user})
        return self.answer


class FakeAuditor:
    def __init__(self, verdict: str = "pass", notes: list[str] | None = None):
        self.verdict = verdict
        self.notes = notes or []

    def audit(
        self,
        *,
        question: str,
        answer: str,
        citations: Sequence[Citation],
    ) -> dict[str, Any]:
        return {"verdict": self.verdict, "notes": list(self.notes)}


class FakeCragScorer:
    def __init__(self, score: float):
        self.score_value = score

    def score(self, question: str, hits: Sequence[RetrievalHit]) -> float:
        return self.score_value


class FakeRewriter:
    def __init__(self, suffix: str = "?"):
        self.suffix = suffix

    def rewrite(
        self, question: str, *, prior_rewrites: Sequence[str]
    ) -> str:
        base = prior_rewrites[-1] if prior_rewrites else question
        return f"{base} {self.suffix}"


@pytest.fixture
def sample_hits() -> list[RetrievalHit]:
    return [
        {
            "chunk_id": "v1",
            "source": "vector",
            "score": 0.91,
            "content": "GraphRAG combines KG + vector retrieval.",
            "metadata": {},
        },
        {
            "chunk_id": "b1",
            "source": "bm25",
            "score": 0.85,
            "content": "BM25 is a sparse lexical retriever.",
            "metadata": {},
        },
        {
            "chunk_id": "k1",
            "source": "kg",
            "score": 0.72,
            "content": "Knowledge graph encodes entity relations.",
            "metadata": {},
        },
    ]


@pytest.fixture
def fake_retrievers(sample_hits):
    return {
        "vector": FakeRetriever("vector", [sample_hits[0]]),
        "bm25": FakeRetriever("bm25", [sample_hits[1]]),
        "kg": FakeRetriever("kg", [sample_hits[2]]),
    }


@pytest.fixture
def fake_reranker():
    return FakeReranker()


@pytest.fixture
def fake_llm():
    return FakeLLM(answer="GraphRAG fuses vector and KG signals.")


@pytest.fixture
def fake_auditor():
    return FakeAuditor()
