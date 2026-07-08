from app.agents.orchestrator import MultiAgentOrchestrator


def test_orchestrator_returns_trace(monkeypatch):
    orchestrator = MultiAgentOrchestrator()

    monkeypatch.setattr(
        orchestrator.query_agent,
        "analyze",
        lambda query: {
            "intent": "query",
            "entities": [],
            "keywords": ["GraphRAG"],
            "complexity": "medium",
            "requires_multi_hop": False,
            "query_rewrite": query,
            "original_query": query,
        },
    )

    monkeypatch.setattr(
        orchestrator.retrieval_agent,
        "hybrid_search",
        lambda query, entities, top_k=10: {
            "vector_results": [],
            "bm25_results": [],
            "graph_results": {},
            "combined_context": [],
            "warnings": [],
        },
    )

    monkeypatch.setattr(
        orchestrator.verification_agent,
        "verify",
        lambda query, answer, sources: {
            "is_supported": False,
            "hallucination_detected": False,
            "confidence": 0.0,
            "issues": [],
            "source_mapping": {},
        },
    )

    result = orchestrator.process_query("What is GraphRAG?")

    assert "trace" in result
    assert "analysis" in result["trace"]
    assert "retrieval" in result["trace"]
    assert "answer" in result
