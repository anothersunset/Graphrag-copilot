"""Shared test fixtures for Graphrag-copilot backend tests."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def sample_document():
    """Provide a sample document for testing."""
    return {
        "id": "doc-001",
        "content": "GraphRAG combines knowledge graphs with retrieval-augmented generation.",
        "metadata": {"source": "test", "page": 1},
    }


@pytest.fixture
def sample_documents():
    """Provide a list of sample documents for testing."""
    return [
        {
            "id": "doc-001",
            "content": "GraphRAG combines knowledge graphs with RAG.",
            "metadata": {"source": "paper1"},
        },
        {
            "id": "doc-002",
            "content": "FAISS is a library for efficient similarity search.",
            "metadata": {"source": "paper2"},
        },
        {
            "id": "doc-003",
            "content": "FastAPI is a modern web framework for Python.",
            "metadata": {"source": "paper3"},
        },
    ]


@pytest.fixture
def sample_query():
    """Provide a sample query for testing."""
    return "How does GraphRAG work?"


@pytest.fixture
def mock_openai_response():
    """Provide a mock OpenAI chat completion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Test response"))]
    return mock_response
