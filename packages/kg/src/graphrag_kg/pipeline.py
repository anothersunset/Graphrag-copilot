"""One-call GraphRAG index construction.

Ties the index-time stages into a single object so the application layer
doesn't have to orchestrate them by hand::

    chunks ──▶ extract (LLM+gleaning | co-occurrence)
           ──▶ resolve (entity dedup / alias merge)
           ──▶ KnowledgeGraphIndex (networkx)
           ──▶ detect + summarize communities

The result (``GraphRAGIndex``) exposes exactly what query-time needs:
the ``KnowledgeGraphIndex`` for PPR/subgraph retrieval, the
``CommunityReport`` list for global search, and a ``chunk_lookup`` so the
PPR retriever can hydrate hit content. Everything runs offline; inject an
LLM to lift extraction/summary quality.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from .community import ChatFn, CommunitySummarizer, detect_communities
from .extraction import CooccurrenceExtractor, LLMEntityExtractor
from .graph_store import KnowledgeGraphIndex
from .models import CommunityReport, ExtractionResult
from .pagerank import PPRRetriever
from .resolution import EntityResolver

logger = logging.getLogger(__name__)


class _Extractor(Protocol):
    def extract(self, chunk_id: str, text: str) -> ExtractionResult: ...


@dataclass
class Chunk:
    chunk_id: str
    content: str


@dataclass
class GraphRAGIndex:
    graph: KnowledgeGraphIndex
    communities: list[CommunityReport] = field(default_factory=list)
    chunk_texts: dict[str, str] = field(default_factory=dict)

    def chunk_lookup(self, chunk_id: str) -> str:
        return self.chunk_texts.get(chunk_id, "")

    def ppr_retriever(self, **kwargs: Any) -> PPRRetriever:
        """A HippoRAG-style local retriever bound to this index."""
        return PPRRetriever(self.graph, chunk_lookup=self.chunk_lookup, **kwargs)

    def stats(self) -> dict[str, int]:
        return {**self.graph.stats(), "communities": len(self.communities)}


def build_index(
    chunks: Sequence[Chunk | dict],
    *,
    llm: ChatFn | None = None,
    extractor: _Extractor | None = None,
    resolver: EntityResolver | None = None,
    embedder: Any | None = None,
    max_gleanings: int = 1,
    max_community_size: int = 20,
    detect_communities_: bool = True,
    summarize: bool = True,
) -> GraphRAGIndex:
    """Build a full GraphRAG index from raw chunks.

    ``llm`` (``(system, user) -> str``) enables high-quality LLM
    extraction + gleaning and abstractive community summaries. Without
    it, a deterministic co-occurrence extractor + template summaries keep
    the pipeline fully offline.
    """
    if extractor is None:
        extractor = (
            LLMEntityExtractor(llm=llm, max_gleanings=max_gleanings)
            if llm is not None
            else CooccurrenceExtractor()
        )
    resolver = resolver or EntityResolver(embedder=embedder)

    norm_chunks = [
        c if isinstance(c, Chunk) else Chunk(chunk_id=c["chunk_id"], content=c.get("content", ""))
        for c in chunks
    ]

    combined = ExtractionResult()
    for ch in norm_chunks:
        combined = combined.merge(extractor.extract(ch.chunk_id, ch.content))

    resolved = resolver.resolve(combined)
    graph = KnowledgeGraphIndex()
    graph.add(resolved)

    communities: list[CommunityReport] = []
    if detect_communities_:
        communities = detect_communities(graph, max_community_size=max_community_size)
        if summarize:
            communities = CommunitySummarizer(llm=llm).summarize(graph, communities)

    return GraphRAGIndex(
        graph=graph,
        communities=communities,
        chunk_texts={ch.chunk_id: ch.content for ch in norm_chunks},
    )
