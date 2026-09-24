"""Four-route retrieval for GraphRAG Copilot v3.1."""

from .base import AsyncRetriever, RetrievalHit, rrf_fuse
from .bm25 import BM25Document, BM25Retriever
from .community import CommunityRetriever
from .contextual import ContextualizedChunk, ContextualRetrievalGenerator
from .kg import KGRetriever
from .reranker import BGEReranker
from .vector import VectorRetriever
from .web import TavilyAdapter, WebRetriever

__version__ = "0.1.1"

__all__ = [
    "AsyncRetriever",
    "BGEReranker",
    "BM25Document",
    "BM25Retriever",
    "CommunityRetriever",
    "ContextualRetrievalGenerator",
    "ContextualizedChunk",
    "KGRetriever",
    "RetrievalHit",
    "TavilyAdapter",
    "VectorRetriever",
    "WebRetriever",
    "__version__",
    "rrf_fuse",
]
