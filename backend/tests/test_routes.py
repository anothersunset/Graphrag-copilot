"""Tests for app.api.routes API endpoints"""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np


@pytest.fixture(autouse=True)
def mock_all_services():
    """Mock all service dependencies before importing routes."""
    mock_settings = MagicMock()
    mock_settings.VECTOR_STORE_TYPE = "faiss"
    mock_settings.EMBEDDING_DIMENSION = 512
    mock_settings.VECTOR_DB_DIR = MagicMock()
    mock_settings.VECTOR_DB_DIR.__truediv__ = lambda self, x: MagicMock(exists=lambda: False)
    mock_settings.EMBEDDING_MODEL = "test"
    mock_settings.EMBEDDING_DEVICE = "cpu"
    mock_settings.VECTOR_SEARCH_TOP_K = 10
    mock_settings.LLM_MODEL = "test-model"
    mock_settings.RAW_DIR = MagicMock()
    mock_settings.MAX_FILE_SIZE = 10 * 1024 * 1024
    mock_settings.APP_NAME = "test"
    mock_settings.APP_VERSION = "0.1"
    mock_settings.NEO4J_URI = "bolt://localhost"
    mock_settings.ZHIPU_API_KEY = "test"
    mock_settings.ZHIPU_BASE_URL = "https://test.com/v1"
    mock_settings.LLM_API_KEY = "test"
    mock_settings.LLM_BASE_URL = "https://test.com/v1"
    mock_settings.LLM_TEMPERATURE = 0.7
    mock_settings.LLM_MAX_TOKENS = 1024

    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = []
    mock_vector_store.get_stats.return_value = {"type": "faiss", "total_vectors": 0, "dimension": 512, "total_documents": 0}

    mock_embedding = MagicMock()
    mock_embedding.embed_query.return_value = [0.1] * 512
    mock_embedding.embed.return_value = [[0.1] * 512]

    mock_bm25 = MagicMock()
    mock_bm25.search.return_value = []
    mock_bm25.get_stats.return_value = {"total_documents": 0}

    mock_kg = MagicMock()
    mock_kg.get_stats.return_value = {"total_nodes": 0, "total_relations": 0, "status": "ok"}
    mock_kg.graph_rag_search.return_value = {}

    mock_llm = MagicMock()
    mock_doc_parser = MagicMock()
    mock_evidence = MagicMock()

    mock_openai = MagicMock()
    mock_st = MagicMock()

    # Mock the router's dependencies
    mock_orchestrator = MagicMock()
    mock_orchestrator.process_query.return_value = {
        "query": "test",
        "analysis": {},
        "answer": "test answer",
        "reasoning": {},
        "verification": {},
        "sources": [],
        "confidence": 0.8,
        "trace": {},
    }

    patches = {
        "config.settings": MagicMock(settings=mock_settings),
        "app.services.vector_store": MagicMock(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding,
            FAISS_AVAILABLE=True,
        ),
        "app.services.bm25_store": MagicMock(bm25_store=mock_bm25),
        "app.services.kg_service": MagicMock(kg_service=mock_kg),
        "app.services.llm_service": MagicMock(llm_service=mock_llm),
        "app.services.document_parser": MagicMock(doc_parser=mock_doc_parser),
        "app.services.evidence_fusion": MagicMock(evidence_fusion_service=mock_evidence),
        "app.agents.orchestrator": MagicMock(
            orchestrator=mock_orchestrator,
            stream_orchestrator=MagicMock(),
        ),
        "openai": mock_openai,
        "sentence_transformers": mock_st,
    }

    with patch.dict("sys.modules", patches):
        yield


class TestAPIRoutes:
    """Test suite for API route endpoints."""

    def test_health_check(self):
        """健康检查端点应返回 200。"""
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_system_status(self):
        """系统状态端点应返回运行信息。"""
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        response = client.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_vector_stats(self):
        """向量统计端点应返回统计信息。"""
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        response = client.get("/api/vector/stats")
        assert response.status_code == 200

    def test_query_endpoint_exists(self):
        """查询端点应存在（不返回 404）。"""
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        response = client.post("/api/query", json={"query": "test"})
        assert response.status_code != 404

    def test_graph_stats(self):
        """图谱统计端点应返回统计信息。"""
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        response = client.get("/api/graph/stats")
        assert response.status_code == 200
