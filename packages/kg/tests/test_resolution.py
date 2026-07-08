"""Entity resolution: normalization merge, similarity merge, relation remap."""

from __future__ import annotations

from typing import ClassVar

from graphrag_kg.models import EntityRecord, ExtractionResult, RelationRecord
from graphrag_kg.resolution import EntityResolver, normalize_name


def test_normalize_name_folds_case_width_and_punct():
    assert normalize_name("Neo4j") == normalize_name("neo4j")
    assert normalize_name("Ｎｅｏ４ｊ") == normalize_name("Neo4j")  # full-width NFKC
    assert normalize_name("知识 图谱") == normalize_name("知识图谱")


def test_case_variants_merge_with_alias_and_provenance_union():
    result = ExtractionResult(
        entities=[
            EntityRecord(name="Neo4j", type="Technology", source_chunk_ids=["c1", "c2"]),
            EntityRecord(name="neo4j", type="Technology", source_chunk_ids=["c3"],
                         description="图数据库"),
        ],
        relations=[
            RelationRecord(source="neo4j", target="Cypher", type="USES",
                           source_chunk_ids=["c3"]),
        ],
    )
    resolved = EntityResolver().resolve(result)

    neo = next(e for e in resolved.entities if e.name == "Neo4j")
    assert "neo4j" in neo.aliases
    assert set(neo.source_chunk_ids) == {"c1", "c2", "c3"}
    assert "图数据库" in neo.description
    # relation endpoint remapped to canonical name
    assert resolved.relations[0].source == "Neo4j"


def test_similarity_merge_via_injected_embedder():
    class TableEmbedder:
        _table: ClassVar[dict[str, list[float]]] = {
            "知识图谱": [1.0, 0.0],
            "KG知识图谱": [0.99, 0.05],
            "向量检索": [0.0, 1.0],
        }

        def embed(self, text: str) -> list[float]:
            for key, vec in self._table.items():
                if key in text.replace(" ", ""):
                    return vec
            return [0.5, 0.5]

    result = ExtractionResult(
        entities=[
            EntityRecord(name="知识图谱", type="Concept", source_chunk_ids=["c1"]),
            EntityRecord(name="KG知识图谱", type="Concept", source_chunk_ids=["c2"]),
            EntityRecord(name="向量检索", type="Concept", source_chunk_ids=["c3"]),
        ]
    )
    resolved = EntityResolver(embedder=TableEmbedder(), threshold=0.9).resolve(result)
    names = sorted(e.name for e in resolved.entities)
    assert len(names) == 2
    assert "向量检索" in names


def test_type_gating_prevents_cross_type_merge():
    result = ExtractionResult(
        entities=[
            EntityRecord(name="Apple", type="Organization"),
            EntityRecord(name="apple", type="Concept"),
        ]
    )
    resolved = EntityResolver().resolve(result)
    assert len(resolved.entities) == 2


def test_self_loops_dropped_and_duplicate_relations_merged():
    result = ExtractionResult(
        entities=[
            EntityRecord(name="GraphRAG", type="Technology", source_chunk_ids=["c1"]),
            EntityRecord(name="graphrag", type="Technology", source_chunk_ids=["c2"]),
            EntityRecord(name="Neo4j", type="Technology", source_chunk_ids=["c1"]),
        ],
        relations=[
            # becomes a self-loop after GraphRAG/graphrag merge
            RelationRecord(source="GraphRAG", target="graphrag", type="RELATED_TO"),
            RelationRecord(source="GraphRAG", target="Neo4j", type="USES",
                           source_chunk_ids=["c1"], confidence=0.6),
            RelationRecord(source="graphrag", target="Neo4j", type="USES",
                           source_chunk_ids=["c2"], confidence=0.9),
        ],
    )
    resolved = EntityResolver().resolve(result)
    assert len(resolved.relations) == 1
    rel = resolved.relations[0]
    assert (rel.source, rel.target, rel.type) == ("GraphRAG", "Neo4j", "USES")
    assert set(rel.source_chunk_ids) == {"c1", "c2"}
    assert rel.confidence == 0.9
