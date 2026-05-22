"""Qdrant-backed dense retriever using bge-large-zh-v1.5 embeddings."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any

from .base import RetrievalHit

logger = logging.getLogger(__name__)

# bge-large-zh-v1.5 native dim; the v3.1 spec locks this to 512 via a
# projection layer at index time for storage cost reasons.
DEFAULT_DIM = 512
DEFAULT_MODEL = "BAAI/bge-large-zh-v1.5"


class VectorRetriever:
    """Async-friendly Qdrant retriever.

    The embedder is dependency-injected so tests can pass deterministic
    vectors. In production, wire in a sentence-transformers model or a
    LiteLLM embedding endpoint.
    """

    name = "vector"

    def __init__(
        self,
        *,
        url: str = "http://localhost:6333",
        collection: str = "chunks",
        embedder: Any | None = None,
        dim: int = DEFAULT_DIM,
        timeout_s: float = 10.0,
    ) -> None:
        self.url = url
        self.collection = collection
        self.dim = dim
        self.timeout_s = timeout_s
        self._embedder = embedder
        self._client: Any | None = None
        self._consecutive_failures = 0
        self._breaker_open_until: float = 0.0

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self.url, timeout=self.timeout_s)
        return self._client

    def _embed(self, text: str) -> list[float]:
        if self._embedder is None:
            raise RuntimeError(
                "VectorRetriever has no embedder injected. Pass an `embedder=` "
                "with an `embed(text: str) -> list[float]` method."
            )
        vec = self._embedder.embed(text)
        if len(vec) != self.dim:
            raise ValueError(f"embedding dim {len(vec)} != expected {self.dim}")
        return vec

    async def aretrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        # Lightweight circuit breaker: bail fast for 30s after 5 consecutive failures.
        if self._breaker_open_until > time.monotonic():
            logger.warning("vector retriever circuit-breaker open, returning []")
            return []

        try:
            vector = self._embed(query)
            results = self.client.search(
                collection_name=self.collection,
                query_vector=vector,
                limit=top_k,
                with_payload=True,
            )
        except Exception:
            logger.exception("vector retrieval failed for query=%r", query)
            self._consecutive_failures += 1
            if self._consecutive_failures >= 5:
                self._breaker_open_until = time.monotonic() + 30.0
            return []

        self._consecutive_failures = 0
        return [self._point_to_hit(p) for p in results]

    @staticmethod
    def _point_to_hit(point: Any) -> RetrievalHit:
        payload = getattr(point, "payload", {}) or {}
        return {
            "chunk_id": str(payload.get("chunk_id") or getattr(point, "id", "")),
            "source": "vector",
            "score": float(getattr(point, "score", 0.0)),
            "content": str(payload.get("content", "")),
            "metadata": {k: v for k, v in payload.items() if k not in {"chunk_id", "content"}},
        }

    @classmethod
    def from_hits(cls, hits: Sequence[RetrievalHit]) -> _StaticVectorRetriever:
        """Construct a test-only retriever that returns a fixed list."""
        return _StaticVectorRetriever(hits)


class _StaticVectorRetriever:
    """Test double for VectorRetriever."""

    name = "vector"

    def __init__(self, hits: Sequence[RetrievalHit]) -> None:
        self._hits = list(hits)

    async def aretrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        return list(self._hits)[:top_k]
