"""KG retriever — static-triples test double."""
from __future__ import annotations

import asyncio

from graphrag_retrieval.kg import KGRetriever


def test_static_triples_render_as_natural_language_hits():
    retriever = KGRetriever.from_triples(
        [
            ("GraphRAG", "BUILT_ON", "LangGraph"),
            ("GraphRAG", "USES", "Neo4j"),
        ]
    )
    hits = asyncio.run(retriever.aretrieve("what is graphrag", top_k=5))
    assert len(hits) == 2
    assert hits[0]["source"] == "kg"
    assert "GraphRAG" in hits[0]["content"]
    assert hits[0]["metadata"]["relation"] == "BUILT_ON"
    # decreasing rank scores
    assert hits[0]["score"] >= hits[1]["score"]


def test_static_empty():
    retriever = KGRetriever.from_triples([])
    hits = asyncio.run(retriever.aretrieve("q", top_k=5))
    assert hits == []
