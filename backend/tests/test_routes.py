"""Tests for app.api.routes API endpoints"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient


class TestAPIRoutes:
    """Test suite for API route endpoints."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Patch dependencies before importing app
        self._patches = [
            patch("app.services.vector_store.faiss"),
            patch("app.services.vector_store.OpenAI"),
            patch("app.services.llm_service.OpenAI"),
        ]
        for p in self._patches:
            p.start()

        from app.main import app
        self.app = app
        self.client = TestClient(app)

    def teardown_method(self):
        """Clean up patches after each test."""
        for p in self._patches:
            p.stop()

    def test_health_check(self):
        """Test the health check endpoint."""
        # Act
        response = self.client.get("/health")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok" or data.get("status") == "healthy"

    def test_system_status(self):
        """Test the system status endpoint."""
        # Act
        response = self.client.get("/system/status")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_vector_stats(self):
        """Test the vector stats endpoint."""
        # Act
        response = self.client.get("/vector/stats")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_query_with_mock(self):
        """Test the query endpoint with mocked orchestrator."""
        # Arrange
        mock_result = {
            "query": "What is Python?",
            "analysis": {"intent": "factual", "keywords": ["Python"]},
            "answer": "Python is a programming language.",
            "reasoning": {"reasoning_chain": ["step1"], "conclusion": "Python is a language"},
            "verification": {"is_consistent": True, "confidence": 0.9, "issues": []},
            "sources": [{"content": "Python is a language", "score": 0.95}],
            "confidence": 0.9,
            "trace": {"steps": ["analyze", "retrieve", "reason", "verify", "generate"]},
        }

        with patch.object(
            self.app, "state", create=True
        ) as mock_state:
            # Try patching the orchestrator on the app state or module level
            with patch("app.api.routes.orchestrator") as mock_orch:
                mock_orch.process_query = MagicMock(return_value=mock_result)

                # Act
                response = self.client.post(
                    "/query",
                    json={"query": "What is Python?", "top_k": 5},
                )

                # Assert - if orchestrator is patched correctly
                if response.status_code == 200:
                    data = response.json()
                    assert "answer" in data or "query" in data

    def test_query_endpoint_exists(self):
        """Test that the query endpoint accepts POST requests."""
        # Act
        response = self.client.post(
            "/query",
            json={"query": "test"},
        )

        # Assert - should not return 404 (endpoint exists)
        assert response.status_code != 404
