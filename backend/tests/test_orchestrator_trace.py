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

    result = orchestrator.process_query("什么是 GraphRAG？")

    assert "trace" in result
    assert "analysis" in result["trace"]
    assert "retrieval" in result["trace"]
    assert "answer" in result
