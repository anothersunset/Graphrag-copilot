"""v3.2 KG retriever multi-hop path round-trip."""

from __future__ import annotations

import asyncio

from graphrag_retrieval.kg import KGRetriever

PATH_2HOP = {
    "nodes": [
        {"id": "GraphRAG", "name": "GraphRAG", "labels": ["Method"], "properties": {}},
        {"id": "Neo4j", "name": "Neo4j", "labels": ["Tech"], "properties": {}},
        {"id": "Cypher", "name": "Cypher", "labels": ["Lang"], "properties": {}},
    ],
    "rels": [
        {"source_id": "GraphRAG", "target_id": "Neo4j", "type": "USES", "properties": {}},
        {"source_id": "Neo4j", "target_id": "Cypher", "type": "QUERIED_BY", "properties": {}},
    ],
    "depth": 2,
}

PATH_1HOP = {
    "nodes": [
        {"id": "GraphRAG", "name": "GraphRAG", "labels": ["Method"], "properties": {}},
        {"id": "BM25", "name": "BM25", "labels": ["Algo"], "properties": {}},
    ],
    "rels": [{"source_id": "GraphRAG", "target_id": "BM25", "type": "USES", "properties": {}}],
    "depth": 1,
}


def test_multi_hop_path_round_trips_into_hit():
    retriever = KGRetriever.from_paths([PATH_2HOP, PATH_1HOP])
    hits = asyncio.run(retriever.aretrieve("how does GraphRAG use Neo4j?", top_k=5))
    assert len(hits) == 2
    assert hits[0]["source"] == "kg"
    # path payload preserved
    assert hits[0]["path"]["depth"] == 2
    assert [n["id"] for n in hits[0]["path"]["nodes"]] == ["GraphRAG", "Neo4j", "Cypher"]
    # rendered content reflects the chain
    assert "GraphRAG" in hits[0]["content"]
    assert "→ Cypher" in hits[0]["content"]


def test_visited_node_ids_aggregate_across_paths():
    retriever = KGRetriever.from_paths([PATH_2HOP, PATH_1HOP])
    hits = asyncio.run(retriever.aretrieve("q", top_k=5))
    # top hit broadcasts the union of all visited node ids
    visited = set(hits[0]["visited_node_ids"])
    assert visited == {"GraphRAG", "Neo4j", "Cypher", "BM25"}


def test_explicit_visited_override():
    retriever = KGRetriever.from_paths([PATH_1HOP], visited=["GraphRAG", "BM25", "DistractorNode"])
    hits = asyncio.run(retriever.aretrieve("q", top_k=5))
    assert "DistractorNode" in hits[0]["visited_node_ids"]


def test_legacy_from_triples_still_works():
    retriever = KGRetriever.from_triples([("A", "REL", "B")])
    hits = asyncio.run(retriever.aretrieve("q", top_k=5))
    assert hits[0]["path"]["depth"] == 1
    assert hits[0]["path"]["rels"][0]["type"] == "REL"
