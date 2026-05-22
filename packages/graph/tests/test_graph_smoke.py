"""End-to-end smoke test: graph runs and produces an answer."""
from __future__ import annotations

from graphrag_graph import GraphConfig, build_graph, initial_state


def test_graph_runs_with_fakes_and_emits_answer(
    fake_retrievers, fake_reranker, fake_llm, fake_auditor
):
    graph = build_graph(
        GraphConfig(),
        retrievers=fake_retrievers,
        reranker=fake_reranker,
        llm_client=fake_llm,
        auditor_client=fake_auditor,
    )
    result = graph.invoke(initial_state("What is GraphRAG?"))

    assert result["answer"]
    assert result["auditor_verdict"] in {"pass", "warn", "fail"}
    assert len(result["citations"]) >= 1
    visited = {entry["node"] for entry in result["audit"]}
    assert {
        "planner",
        "retriever",
        "evaluator",
        "generator",
        "auditor",
    } <= visited


def test_graph_runs_with_no_components_uses_skeletons():
    graph = build_graph(GraphConfig())
    result = graph.invoke(initial_state("ping"))
    # Skeleton path: no retrievers → no fused hits → crag=0 → fallback
    assert result["audit"]
    assert result["crag_decision"] == "fallback"
    assert result["auditor_verdict"] == "warn"
