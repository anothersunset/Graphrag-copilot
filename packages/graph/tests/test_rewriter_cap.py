"""Rewriter loop is capped at max_rewrites (locked v3.1 value: 2)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from graphrag_graph import GraphConfig, build_graph, initial_state
from graphrag_graph.crag import CragResult
from graphrag_graph.state import Citation, RetrievalHit


class AlwaysRewriteScorer:
    def score(self, query: str, hits: Sequence[RetrievalHit]) -> CragResult:
        return CragResult(
            score=0.5,
            decision="rewrite",
            relevance=0.5,
            coverage=0.5,
            detail={"test": True},
        )


class StaticRetriever:
    name = "vector"

    def retrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        hit: RetrievalHit = {
            "chunk_id": "v1",
            "source": "vector",
            "score": 0.5,
            "content": "x",
            "metadata": {},
        }
        return [hit][:top_k]


class WarningAuditor:
    def audit(
        self,
        *,
        question: str,
        answer: str,
        citations: Sequence[Citation],
    ) -> dict[str, Any]:
        return {"verdict": "warn", "notes": []}


def test_rewrite_loop_stops_at_cap():
    # Always-mid CRAG score forces rewrite every time.
    scorer = AlwaysRewriteScorer()
    retrievers = {"vector": StaticRetriever()}
    graph = build_graph(
        GraphConfig(max_rewrites=2),
        retrievers=retrievers,
        crag_scorer=scorer,
        auditor_client=WarningAuditor(),
    )
    result = graph.invoke(initial_state("loop test"))

    # After 2 rewrites the next "rewrite" decision falls through to fallback.
    assert result["rewrite_iteration"] == 2
    assert result["crag_decision"] == "rewrite"  # last evaluator decision
    # The compiled graph routed to fallback (rewriter cap), so answer is the
    # fallback message.
    assert "I don't have enough confident evidence" in result["answer"]
