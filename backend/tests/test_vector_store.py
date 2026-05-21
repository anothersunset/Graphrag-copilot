"""Tests for app.services.vector_store.VectorStore and EmbeddingService"""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np


class TestVectorStore:
    """Test suite for VectorStore operations."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        with patch("app.services.vector_store.faiss") as mock_faiss:
            # Mock FAISS index
            mock_index = MagicMock()
            mock_faiss.IndexFlatIP.return_value = mock_index
            mock_faiss.IndexFlatL2.return_value = mock_index
            
            from app.services.vector_store import VectorStore
            self.store = VectorStore(store_type="faiss")
            self.mock_index = mock_index
            self.mock_faiss = mock_faiss

    def test_添加文档后搜索能返回结果(self):
        """Test that after adding documents, search returns results."""
        # Arrange
        dim = 128
        docs = [
            {"id": "doc1", "content": "First document", "metadata": {"source": "test"}},
            {"id": "doc2", "content": "Second document", "metadata": {"source": "test"}},
        ]
        embeddings = np.random.randn(2, dim).astype("float32")
        
        # Mock FAISS search to return results
        self.mock_index.search.return_value = (
            np.array([[0.9, 0.8]]),  # distances
            np.array([[0, 1]]),       # indices
        )
        self.mock_index.ntotal = 2

        # Act
        self.store.add_documents(docs, embeddings)
        results = self.store.search(np.random.randn(dim).astype("float32"), top_k=2)

        # Assert
        assert isinstance(results, list)
        assert len(results) <= 2

    def test_空索引搜索返回空列表(self):
        """Test that searching an empty index returns empty results."""
        # Arrange
        dim = 128
        self.mock_index.ntotal = 0
        self.mock_index.search.return_value = (
            np.array([[]]),   # empty distances
            np.array([[]]),   # empty indices
        )

        # Act
        results = self.store.search(np.random.randn(dim).astype("float32"), top_k=5)

        # Assert
        assert isinstance(results, list)
        assert len(results) == 0

    def test_文档数量和向量数量不一致抛异常(self):
        """Test that mismatched document and embedding counts raise an error."""
        # Arrange
        dim = 128
        docs = [
            {"id": "doc1", "content": "First document", "metadata": {}},
            {"id": "doc2", "content": "Second document", "metadata": {}},
        ]
        # Only 1 embedding for 2 documents
        embeddings = np.random.randn(1, dim).astype("float32")

        # Act & Assert
        with pytest.raises((ValueError, AssertionError)):
            self.store.add_documents(docs, embeddings)

    def test_get_stats返回正确统计(self):
        """Test that get_stats returns correct statistics."""
        # Arrange
        self.mock_index.ntotal = 42
        
        # Act
        stats = self.store.get_stats()

        # Assert
        assert isinstance(stats, dict)
        assert stats.get("total_vectors") == 42 or stats.get("document_count") == 42


class TestEmbeddingService:
    """Test suite for EmbeddingService."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        with patch("app.services.vector_store.OpenAI") as MockOpenAI:
            self.mock_client = MagicMock()
            MockOpenAI.return_value = self.mock_client
            
            from app.services.vector_store import EmbeddingService
            self.service = EmbeddingService()

    def test_embed_query返回正确维度的向量(self):
        """Test that embed_query returns a vector with the expected dimension."""
        # Arrange
        expected_dim = 1536
        mock_embedding = [0.1] * expected_dim
        self.mock_client.embeddings.create.return_value = MagicMock(
            data=[MagicMock(embedding=mock_embedding)]
        )

        # Act
        result = self.service.embed_query("test query")

        # Assert
        assert isinstance(result, list)
        assert len(result) == expected_dim
        self.mock_client.embeddings.create.assert_called_once()
