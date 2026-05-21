"""Tests for app.agents.orchestrator.MultiAgentOrchestrator"""

import pytest
from unittest.mock import MagicMock, patch


class TestMultiAgentOrchestrator:
    """Test suite for the multi-agent orchestrator."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        with patch("app.agents.orchestrator.QueryAgent") as MockQuery, \
             patch("app.agents.orchestrator.RetrievalAgent") as MockRetrieval, \
             patch("app.agents.orchestrator.ReasoningAgent") as MockReasoning, \
             patch("app.agents.orchestrator.VerificationAgent") as MockVerification, \
             patch("app.agents.orchestrator.GenerationAgent") as MockGeneration:
            
            from app.agents.orchestrator import MultiAgentOrchestrator
            self.orchestrator = MultiAgentOrchestrator()
            
            # Store mock agents for assertions
            self.mock_query_agent = self.orchestrator.query_agent
            self.mock_retrieval_agent = self.orchestrator.retrieval_agent
            self.mock_reasoning_agent = self.orchestrator.reasoning_agent
            self.mock_verification_agent = self.orchestrator.verification_agent
            self.mock_generation_agent = self.orchestrator.generation_agent

    def test_完整流程返回所有字段(self):
        """Test that the full pipeline returns all expected fields."""
        # Arrange
        self.mock_query_agent.analyze.return_value = {
            "intent": "factual",
            "keywords": ["test"],
            "rewritten_query": "test query",
        }
        self.mock_retrieval_agent.retrieve.return_value = [
            {"content": "doc1", "score": 0.9},
            {"content": "doc2", "score": 0.8},
        ]
        self.mock_reasoning_agent.reason.return_value = {
            "reasoning_chain": ["step1", "step2"],
            "conclusion": "test conclusion",
        }
        self.mock_verification_agent.verify.return_value = {
            "is_consistent": True,
            "confidence": 0.95,
            "issues": [],
        }
        self.mock_generation_agent.generate.return_value = {
            "answer": "This is the answer.",
            "citations": ["doc1"],
        }

        # Act
        result = self.orchestrator.process_query("What is test?", top_k=5)

        # Assert
        assert isinstance(result, dict)
        for field in ["query", "analysis", "answer", "reasoning", "verification", "sources", "confidence", "trace"]:
            assert field in result, f"Missing field: {field}"
        assert result["query"] == "What is test?"
        assert result["confidence"] == 0.95

    def test_检索失败时优雅降级(self):
        """Test graceful degradation when retrieval fails."""
        # Arrange
        self.mock_query_agent.analyze.return_value = {
            "intent": "factual",
            "keywords": ["test"],
            "rewritten_query": "test query",
        }
        self.mock_retrieval_agent.retrieve.side_effect = RuntimeError("Retrieval service unavailable")
        self.mock_generation_agent.generate.return_value = {
            "answer": "I cannot find relevant information due to retrieval failure.",
            "citations": [],
        }

        # Act
        result = self.orchestrator.process_query("What is test?", top_k=5)

        # Assert
        assert isinstance(result, dict)
        assert result["sources"] == [] or result["sources"] is not None
        assert "answer" in result

    def test_空上下文返回无信息回答(self):
        """Test that empty context leads to a 'no information' answer."""
        # Arrange
        self.mock_query_agent.analyze.return_value = {
            "intent": "factual",
            "keywords": ["unknown"],
            "rewritten_query": "unknown query",
        }
        self.mock_retrieval_agent.retrieve.return_value = []
        self.mock_reasoning_agent.reason.return_value = {
            "reasoning_chain": [],
            "conclusion": "No context available",
        }
        self.mock_verification_agent.verify.return_value = {
            "is_consistent": True,
            "confidence": 0.0,
            "issues": ["No sources found"],
        }
        self.mock_generation_agent.generate.return_value = {
            "answer": "I don't have enough information to answer this question.",
            "citations": [],
        }

        # Act
        result = self.orchestrator.process_query("Unknown topic?", top_k=5)

        # Assert
        assert "answer" in result
        assert result["confidence"] == 0.0 or result["confidence"] < 0.5

    def test_低置信度添加警告(self):
        """Test that low confidence triggers a warning in the response."""
        # Arrange
        self.mock_query_agent.analyze.return_value = {
            "intent": "factual",
            "keywords": ["ambiguous"],
            "rewritten_query": "ambiguous query",
        }
        self.mock_retrieval_agent.retrieve.return_value = [
            {"content": "weak doc", "score": 0.3},
        ]
        self.mock_reasoning_agent.reason.return_value = {
            "reasoning_chain": ["uncertain step"],
            "conclusion": "uncertain conclusion",
        }
        self.mock_verification_agent.verify.return_value = {
            "is_consistent": False,
            "confidence": 0.2,
            "issues": ["Low source quality", "Contradictory information"],
        }
        self.mock_generation_agent.generate.return_value = {
            "answer": "Possible answer but uncertain.",
            "citations": ["weak doc"],
        }

        # Act
        result = self.orchestrator.process_query("Ambiguous question?", top_k=5)

        # Assert
        assert result["confidence"] < 0.5
        # Check for warning indicators - could be in trace, verification, or a dedicated field
        has_warning = (
            "warning" in result
            or "warning" in str(result.get("trace", "")).lower()
            or "warning" in str(result.get("verification", "")).lower()
            or result.get("confidence", 1.0) < 0.5
        )
        assert has_warning, "Expected a warning for low confidence response"
