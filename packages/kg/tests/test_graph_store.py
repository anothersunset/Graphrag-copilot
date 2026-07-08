"""KnowledgeGraphIndex: build, lookup, traversal, Neo4j export."""

from __future__ import annotations

from graphrag_kg.graph_store import KnowledgeGraphIndex
from graphrag_kg.models import EntityRecord, ExtractionResult, RelationRecord


def _small_result() -> ExtractionResult:
    return ExtractionResult(
        entities=[
            EntityRecord(name="GraphRAG", type="Technology", description="graph-based RAG",
                         source_chunk_ids=["c1"], aliases=["Graph RAG"]),
            EntityRecord(name="Neo4j", type="Technology", source_chunk_ids=["c1", "c2"]),
            EntityRecord(name="Cypher", type="Technology", source_chunk_ids=["c2"]),
        ],
        relations=[
            RelationRecord(source="GraphRAG", target="Neo4j", type="USES",
                           confidence=0.8, source_chunk_ids=["c1"]),
            RelationRecord(source="Neo4j", target="Cypher", type="DEPENDS_ON",
                           confidence=0.7, source_chunk_ids=["c2"]),
        ],
    )


def test_add_and_lookup_via_alias():
    idx = KnowledgeGraphIndex()
    idx.add(_small_result())
    assert idx.stats()["nodes"] == 3
    assert idx.resolve_name("graph rag") == "GraphRAG"  # alias, case+space folded
    assert idx.match_entities(["neo4j", "unknown"]) == ["Neo4j"]
    assert set(idx.chunk_ids_for("Neo4j")) == {"c1", "c2"}


def test_repeated_evidence_accumulates_edge_weight():
    idx = KnowledgeGraphIndex()
    idx.add(_small_result())
    w1 = idx.graph.edges["GraphRAG", "Neo4j"]["weight"]
    idx.add(_small_result())
    w2 = idx.graph.edges["GraphRAG", "Neo4j"]["weight"]
    assert w2 > w1
    assert idx.stats()["nodes"] == 3  # no duplicate nodes


def test_subgraph_paths_shape_and_depth_cap():
    idx = KnowledgeGraphIndex()
    idx.add(_small_result())
    paths = idx.subgraph_paths(["GraphRAG"], max_depth=2, branch_limit=8)
    assert paths, "expected at least one path from the seed"
    for p in paths:
        assert set(p) == {"nodes", "rels", "depth"}
        assert len(p["nodes"]) == p["depth"] + 1
        assert len(p["rels"]) == p["depth"]
        assert p["depth"] <= 2
    # the 2-hop chain GraphRAG → Neo4j → Cypher must be reachable
    rendered = [tuple(n["id"] for n in p["nodes"]) for p in paths]
    assert ("GraphRAG", "Neo4j", "Cypher") in rendered


def test_to_neo4j_rows_match_v1_ingest_contract():
    idx = KnowledgeGraphIndex()
    idx.add(_small_result())
    entities, relations = idx.to_neo4j_rows()
    assert {e["name"] for e in entities} == {"GraphRAG", "Neo4j", "Cypher"}
    for e in entities:
        assert set(e) == {"name", "type", "confidence", "properties"}
    for r in relations:
        assert set(r) == {"source", "target", "type", "properties"}
        assert r["properties"]["weight"] > 0
