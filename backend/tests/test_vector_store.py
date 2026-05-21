"""Tests for app.services.vector_store.VectorStore and EmbeddingService"""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings and sentence_transformers."""
    mock_settings = MagicMock()
    mock_settings.VECTOR_STORE_TYPE = "faiss"
    mock_settings.EMBEDDING_DIMENSION = 512
    mock_settings.VECTOR_DB_DIR = MagicMock()
    mock_settings.VECTOR_DB_DIR.__truediv__ = lambda self, x: MagicMock(exists=lambda: False)
    mock_settings.EMBEDDING_MODEL = "test-model"
    mock_settings.EMBEDDING_DEVICE = "cpu"
    mock_settings.VECTOR_SEARCH_TOP_K = 10

    mock_st = MagicMock()
    mock_model = MagicMock()
    mock_model.encode.return_value = np.random.randn(2, 512).astype("float32")
    mock_st.SentenceTransformer.return_value = mock_model

    with patch.dict("sys.modules", {
        "config.settings": MagicMock(settings=mock_settings),
        "sentence_transformers": mock_st,
    }):
        yield mock_settings, mock_model


class TestEmbeddingService:
    """Test suite for EmbeddingService."""

    def test_embed_query返回正确维度的向量(self, mock_settings):
        """embed_query 应返回 512 维向量。"""
        mock_settings_tuple, mock_model = mock_settings
        mock_model.encode.return_value = np.random.randn(1, 512).astype("float32")

        from app.services.vector_store import EmbeddingService
        service = EmbeddingService()
        result = service.embed_query("test query")

        assert isinstance(result, list)
        assert len(result) == 512

    def test_embed批量编码(self, mock_settings):
        """embed 应为每个文本返回一个向量。"""
        mock_settings_tuple, mock_model = mock_settings
        mock_model.encode.return_value = np.random.randn(2, 512).astype("float32")

        from app.services.vector_store import EmbeddingService
        service = EmbeddingService()
        results = service.embed(["hello", "world"])

        assert isinstance(results, list)
        assert len(results) == 2

    def test_hash_fallback模式(self, mock_settings):
        """当 sentence_transformers 不可用时，应降级为 hash embed。"""
        mock_settings_tuple, mock_model = mock_settings

        with patch.dict("sys.modules", {"sentence_transformers": None}):
            from app.services.vector_store import EmbeddingService
            service = EmbeddingService()
            assert service.use_tfidf is True
            result = service.embed_query("fallback test")
            assert len(result) == 512
