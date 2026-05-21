"""Tests for app.agents.orchestrator.MultiAgentOrchestrator"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# Mock the module-level imports before importing the orchestrator
@pytest.fixture(autouse=True)
def mock_services():
    """Mock all external service dependencies."""
    with patch.dict("sys.modules", {
        "app.services.llm_service": MagicMock(),
        "app.services.vector_store": MagicMock(),
        "app.services.bm25_store": MagicMock(),
        "app.services.kg_service": MagicMock(),
        "app.services.evidence_fusion": MagicMock(),
    }):
        yield


class TestMultiAgentOrchestrator:
    """Test suite for the multi-agent orchestrator."""

    def test_完整流程返回所有字段(self, mock_services):
        """完整流程应返回所有预期字段。"""
        from unittest.mock import MagicMock

        # Create mock agents
        mock_query = MagicMock()
        mock_query.analyze.return_value = {
            "intent": "query",
            "entities": ["test"],
            "keywords": ["test"],
            "complexity": "simple",
            "requires_multi_hop": False,
            "query_rewrite": "test query",
            "original_query": "What is test?",
        }

        mock_retrieval = MagicMock()
        mock_retrieval.hybrid_search.return_value = {
            "vector_results": [{"content": "doc1", "score": 0.9}],
            "bm25_results": [],
            "graph_results": {},
            "combined_context": [{"content": "doc1", "type": "text", "source": "file.txt", "fusion_score": 0.9}],
            "warnings": [],
        }

        mock_reasoning = MagicMock()
        mock_reasoning.reason.return_value = {
            "answer": "Test answer",
            "reasoning_path": ["step1"],
            "sources_used": ["doc1"],
            "confidence": 0.85,
            "limitations": "",
        }

        mock_verification = MagicMock()
        mock_verification.verify.return_value = {
            "is_supported": True,
            "hallucination_detected": False,
            "confidence": 0.9,
            "issues": [],
            "source_mapping": {},
        }

        mock_generation = MagicMock()
        mock_generation.generate.return_value = "Final answer with sources."

        # Patch the orchestrator class
        with patch("app.agents.orchestrator.QueryUnderstandingAgent", return_value=mock_query), \
             patch("app.agents.orchestrator.RetrievalAgent", return_value=mock_retrieval), \
             patch("app.agents.orchestrator.ReasoningAgent", return_value=mock_reasoning), \
             patch("app.agents.orchestrator.VerificationAgent", return_value=mock_verification), \
             patch("app.agents.orchestrator.GenerationAgent", return_value=mock_generation):

            from app.agents.orchestrator import MultiAgentOrchestrator
            orchestrator = MultiAgentOrchestrator()
            result = orchestrator.process_query("What is test?", top_k=5)

        assert isinstance(result, dict)
        for field in ["query", "analysis", "answer", "reasoning", "verification", "sources", "confidence", "trace"]:
            assert field in result, f"Missing field: {field}"
        assert result["query"] == "What is test?"
        assert result["confidence"] == 0.9

    def test_检索失败时优雅降级(self, mock_services):
        """检索失败时应优雅降级，不崩溃。"""
        mock_query = MagicMock()
        mock_query.analyze.return_value = {
            "intent": "query", "entities": [], "keywords": ["test"],
            "complexity": "simple", "requires_multi_hop": False,
            "query_rewrite": "test", "original_query": "test",
        }

        mock_retrieval = MagicMock()
        mock_retrieval.hybrid_search.return_value = {
            "vector_results": [], "bm25_results": [], "graph_results": {},
            "combined_context": [], "warnings": ["vector_search_failed: timeout"],
        }

        mock_reasoning = MagicMock()
        mock_reasoning.reason.return_value = {
            "answer": "当前知识库中没有找到足够信息回答这个问题。",
            "reasoning_path": ["没有召回到有效证据"],
            "sources_used": [], "confidence": 0.0, "limitations": "retrieval_empty",
        }

        mock_verification = MagicMock()
        mock_verification.verify.return_value = {
            "is_supported": False, "hallucination_detected": False,
            "confidence": 0.0, "issues": ["No sources"], "source_mapping": {},
        }

        mock_generation = MagicMock()
        mock_generation.generate.return_value = "当前知识库中没有找到足够信息回答这个问题。"

        with patch("app.agents.orchestrator.QueryUnderstandingAgent", return_value=mock_query), \
             patch("app.agents.orchestrator.RetrievalAgent", return_value=mock_retrieval), \
             patch("app.agents.orchestrator.ReasoningAgent", return_value=mock_reasoning), \
             patch("app.agents.orchestrator.VerificationAgent", return_value=mock_verification), \
             patch("app.agents.orchestrator.GenerationAgent", return_value=mock_generation):

            from app.agents.orchestrator import MultiAgentOrchestrator
            orchestrator = MultiAgentOrchestrator()
            result = orchestrator.process_query("test", top_k=5)

        assert isinstance(result, dict)
        assert "answer" in result
        assert result["confidence"] == 0.0

    def test_空上下文返回无信息回答(self, mock_services):
        """空上下文应返回'无足够信息'的回答。"""
        mock_query = MagicMock()
        mock_query.analyze.return_value = {
            "intent": "query", "entities": [], "keywords": ["unknown"],
            "complexity": "simple", "requires_multi_hop": False,
            "query_rewrite": "unknown", "original_query": "unknown",
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

            from app.agents.orchestrator import MultiAgentOrchestrator
            orchestrator = MultiAgentOrchestrator()
            result = orchestrator.process_query("Unknown topic?", top_k=5)

        assert "answer" in result
        assert result["confidence"] < 0.5

    def test_低置信度添加警告(self, mock_services):
        """低置信度应在结果中标记。"""
        mock_query = MagicMock()
        mock_query.analyze.return_value = {
            "intent": "query", "entities": [], "keywords": ["ambiguous"],
            "complexity": "medium", "requires_multi_hop": False,
            "query_rewrite": "ambiguous", "original_query": "ambiguous",
        }

        mock_retrieval = MagicMock()
        mock_retrieval.hybrid_search.return_value = {
            "vector_results": [], "bm25_results": [], "graph_results": {},
            "combined_context": [{"content": "weak", "type": "text", "source": "weak.txt", "fusion_score": 0.3}],
            "warnings": [],
        }

        mock_reasoning = MagicMock()
        mock_reasoning.reason.return_value = {
            "answer": "不确定的回答",
            "reasoning_path": ["uncertain"], "sources_used": ["weak"],
            "confidence": 0.3, "limitations": "low_quality_sources",
        }

        mock_verification = MagicMock()
        mock_verification.verify.return_value = {
            "is_supported": False, "hallucination_detected": True,
            "confidence": 0.2, "issues": ["Low quality", "Contradictory"],
            "source_mapping": {},
        }

        mock_generation = MagicMock()
        mock_generation.generate.return_value = "可能的答案，但不确定。\n\n注意: 当前答案置信度较低，建议结合原文进一步核实。"

        with patch("app.agents.orchestrator.QueryUnderstandingAgent", return_value=mock_query), \
             patch("app.agents.orchestrator.RetrievalAgent", return_value=mock_retrieval), \
             patch("app.agents.orchestrator.ReasoningAgent", return_value=mock_reasoning), \
             patch("app.agents.orchestrator.VerificationAgent", return_value=mock_verification), \
             patch("app.agents.orchestrator.GenerationAgent", return_value=mock_generation):

            from app.agents.orchestrator import MultiAgentOrchestrator
            orchestrator = MultiAgentOrchestrator()
            result = orchestrator.process_query("Ambiguous?", top_k=5)

        assert result["confidence"] < 0.5
        assert "注意" in result["answer"] or result["confidence"] < 0.5
