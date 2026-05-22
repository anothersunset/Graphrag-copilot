"""Rewriter loop is capped at max_rewrites (locked v3.1 value: 2)."""

from __future__ import annotations

from graphrag_graph import GraphConfig, build_graph, initial_state

from .conftest import FakeAuditor, FakeCragScorer, FakeRetriever


def test_rewrite_loop_stops_at_cap():
    # Always-mid CRAG score forces rewrite every time.
    scorer = FakeCragScorer(score=0.5)
    retrievers = {
        "vector": FakeRetriever(
            "vector",
            [
                {
                    "chunk_id": "v1",
                    "source": "vector",
                    "score": 0.5,
                    "content": "x",
                }
            ],
        )
    }
    graph = build_graph(
        GraphConfig(max_rewrites=2),
        retrievers=retrievers,
        crag_scorer=scorer,
        auditor_client=FakeAuditor(verdict="warn"),
    )
    result = graph.invoke(initial_state("loop test"))

    # After 2 rewrites the next "rewrite" decision falls through to fallback.
    assert result["rewrite_iteration"] == 2
    assert result["crag_decision"] == "rewrite"  # last evaluator decision
    # The compiled graph routed to fallback (rewriter cap), so answer is the
    # fallback message.
    assert "I don't have enough confident evidence" in result["answer"]
