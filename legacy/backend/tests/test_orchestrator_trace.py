"""Tests for orchestrator trace output."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def mock_services():
    """Mock all external service dependencies."""
    with patch.dict("sys.modules", {
        "app.services.llm_service": MagicMock(),
        "app.services.vector_store": MagicMock(),
        "app.services.bm25_store": MagicMock(),
        "app.services.kg_service": MagicMock(),
        "app.services.evidence_fusion": MagicMock(),
        "graphrag_graph.graph": MagicMock(),
        "graphrag_graph.config": MagicMock(),
        "graphrag_graph.state": MagicMock(),
        "app.agents.retriever_adapters": MagicMock(),
    }):
        yield


def test_legacy_orchestrator_returns_trace(mock_services):
    """LegacyOrchestrator 应返回 trace 字段。"""
    mock_query = MagicMock()
    mock_query.analyze.return_value = {
        "intent": "query", "entities": [], "keywords": ["GraphRAG"],
        "complexity": "medium", "requires_multi_hop": False,
        "query_rewrite": "什么是 GraphRAG？", "original_query": "什么是 GraphRAG？",
    }

    mock_retrieval = MagicMock()
    mock_retrieval.hybrid_search.return_value = {
        "vector_results": [], "bm25_results": [], "graph_results": {},
        "combined_context": [], "warnings": [],
    }

    mock_reasoning = MagicMock()
    mock_reasoning.reason.return_value = {
        "answer": "当前知识库中没有找到足够信息回答这个问题。",
        "reasoning_path": [], "sources_used": [], "confidence": 0.0,
        "limitations": "retrieval_empty",
    }

    mock_verification = MagicMock()
    mock_verification.verify.return_value = {
        "is_supported": False, "hallucination_detected": False,
        "confidence": 0.0, "issues": [], "source_mapping": {},
    }

    mock_generation = MagicMock()
    mock_generation.generate.return_value = "当前知识库中没有找到足够信息回答这个问题。"

    with patch("app.agents.orchestrator.QueryUnderstandingAgent", return_value=mock_query), \
         patch("app.agents.orchestrator.RetrievalAgent", return_value=mock_retrieval), \
         patch("app.agents.orchestrator.ReasoningAgent", return_value=mock_reasoning), \
         patch("app.agents.orchestrator.VerificationAgent", return_value=mock_verification), \
         patch("app.agents.orchestrator.GenerationAgent", return_value=mock_generation):

        from app.agents.orchestrator import LegacyOrchestrator
        orchestrator = LegacyOrchestrator()
        result = orchestrator.process_query("什么是 GraphRAG？")

    assert "trace" in result
    assert "analysis" in result["trace"]
    assert "retrieval" in result["trace"]
    assert "answer" in result


def test_langgraph_orchestrator_returns_trace(mock_services):
    """LangGraphOrchestrator 应返回 trace 字段。"""
    from app.agents.orchestrator import LangGraphOrchestrator
    orchestrator = LangGraphOrchestrator()

    mock_state = {
        "answer": "GraphRAG 是一种图增强的检索增强生成系统。",
        "fused_hits": [],
        "citations": [],
        "audit": [
            {"node": "planner", "summary": "planned"},
            {"node": "retriever", "summary": "retrieved"},
            {"node": "evaluator", "summary": "evaluated"},
            {"node": "generator", "summary": "generated"},
            {"node": "auditor", "summary": "audited"},
        ],
        "crag_score": 0.7,
        "crag_decision": "use",
        "auditor_verdict": "pass",
        "tool_calls": [],
        "rewrite_iteration": 0,
    }

    result = orchestrator._format_response("什么是 GraphRAG？", mock_state)

    assert "trace" in result
    assert "nodes" in result["trace"]
    assert "audit" in result["trace"]
    assert "answer" in result
    assert len(result["trace"]["nodes"]) == 5
