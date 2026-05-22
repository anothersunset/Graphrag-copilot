"""Protocol-typed interfaces for swappable components.

The graph package is wire-only; concrete retriever / reranker / LLM
implementations live in ``packages/retrieval``, ``packages/kg``, and the
application layer respectively. Nodes depend on these Protocols so they can
be unit-tested with fakes.
"""
from __future__ import annotations

from typing import Any, Protocol, Sequence, runtime_checkable

from .state import Citation, RetrievalHit


@runtime_checkable
class Retriever(Protocol):
    """Single-route retriever (vector / BM25 / KG / web)."""

    name: str  # one of {"vector", "bm25", "kg", "web"}

    def retrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        ...


@runtime_checkable
class Reranker(Protocol):
    """Cross-encoder reranker (W3 wires BGE-Reranker-v2-m3)."""

    def rerank(
        self, query: str, hits: Sequence[RetrievalHit], *, top_k: int
    ) -> list[RetrievalHit]:
        ...


@runtime_checkable
class LLMClient(Protocol):
    """LiteLLM-backed LLM client with optional structured output (Instructor)."""

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        response_schema: type | None = None,
        timeout_s: float = 30.0,
    ) -> Any:
        ...


@runtime_checkable
class CragScorer(Protocol):
    """Pluggable CRAG scoring strategy (W4 lands DSPy version)."""

    def score(self, question: str, hits: Sequence[RetrievalHit]) -> float:
        ...


@runtime_checkable
class QueryRewriter(Protocol):
    """Pluggable query rewrite strategy."""

    def rewrite(self, question: str, *, prior_rewrites: Sequence[str]) -> str:
        ...


@runtime_checkable
class AuditorClient(Protocol):
    """Post-generation auditor (W7 DSPy-based judge)."""

    def audit(
        self, *, question: str, answer: str, citations: Sequence[Citation]
    ) -> dict[str, Any]:
        ...
