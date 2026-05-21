"""Four-route retrieval for GraphRAG Copilot v3.1."""
from .base import AsyncRetriever, RetrievalHit, rrf_fuse
from .bm25 import BM25Retriever
from .vector import VectorRetriever

__version__ = "0.1.0"

__all__ = [
    "AsyncRetriever",
    "BM25Retriever",
    "RetrievalHit",
    "VectorRetriever",
    "rrf_fuse",
    "__version__",
]
