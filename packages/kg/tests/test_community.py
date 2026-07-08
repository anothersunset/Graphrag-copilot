"""Louvain community detection + summarization."""

from __future__ import annotations

from graphrag_kg.community import CommunitySummarizer, detect_communities
from graphrag_kg.graph_store import KnowledgeGraphIndex
from graphrag_kg.models import EntityRecord, ExtractionResult, RelationRecord


def _clustered_index() -> KnowledgeGraphIndex:
    """Two dense triangles joined by one weak bridge edge."""
    ents = [
        EntityRecord(name=n, type="Technology", source_chunk_ids=[f"c-{n}"])
        for n in ["A1", "A2", "A3", "B1", "B2", "B3"]
    ]
    strong = 0.9
    rels = [
        RelationRecord(source="A1", target="A2", type="USES", confidence=strong),
        RelationRecord(source="A2", target="A3", type="USES", confidence=strong),
        RelationRecord(source="A1", target="A3", type="USES", confidence=strong),
        RelationRecord(source="B1", target="B2", type="USES", confidence=strong),
        RelationRecord(source="B2", target="B3", type="USES", confidence=strong),
        RelationRecord(source="B1", target="B3", type="USES", confidence=strong),
        RelationRecord(source="A3", target="B1", type="RELATED_TO", confidence=0.1),
    ]
    idx = KnowledgeGraphIndex()
    idx.add(ExtractionResult(entities=ents, relations=rels))
    return idx


def test_detects_the_two_triangles():
    idx = _clustered_index()
    reports = detect_communities(idx, min_community_size=2, seed=42)
    level0 = [r for r in reports if r.level == 0]
    assert len(level0) == 2
    memberships = sorted(tuple(r.entity_ids) for r in level0)
    assert memberships == [("A1", "A2", "A3"), ("B1", "B2", "B3")]
    for r in level0:
        assert r.size == 3
        assert 0.0 < r.rank <= 1.0
        assert len(r.chunk_ids) == 3  # provenance flows through


def test_empty_graph_yields_no_reports():
    assert detect_communities(KnowledgeGraphIndex()) == []


def test_template_summarizer_is_deterministic_offline():
    idx = _clustered_index()
    reports = detect_communities(idx, min_community_size=2, seed=42)
    summarized = CommunitySummarizer().summarize(idx, reports)
    for r in summarized:
        assert r.title
        assert "个实体" in r.summary
        # core entities named in the summary
        assert any(e in r.summary for e in r.entity_ids)


def test_llm_summarizer_uses_first_line_as_title():
    idx = _clustered_index()
    reports = detect_communities(idx, min_community_size=2, seed=42)

    def fake_llm(system: str, user: str) -> str:
        assert "实体" in user  # context prompt contains member entities
        return "图检索技术栈\n该社区围绕图数据库与检索技术展开。"

    summarized = CommunitySummarizer(llm=fake_llm).summarize(idx, reports)
    assert summarized[0].title == "图检索技术栈"
    assert summarized[0].summary.startswith("该社区围绕")


def test_llm_failure_falls_back_to_template():
    idx = _clustered_index()
    reports = detect_communities(idx, min_community_size=2, seed=42)

    def broken_llm(system: str, user: str) -> str:
        raise RuntimeError("api down")

    summarized = CommunitySummarizer(llm=broken_llm).summarize(idx, reports)
    assert all(r.summary for r in summarized)


def test_oversized_community_gets_level1_partition():
    """Hierarchy logic exercised via an injected partition function.

    On graphs this small, Louvain at resolution 1.0 rarely leaves an
    oversize community, so the two-level path is driven deterministically:
    pass 1 lumps everything together, pass 2 (on the subgraph) splits.
    """
    idx = _clustered_index()
    all_nodes = set(idx.graph.nodes)

    calls: list[int] = []

    def fake_partition(graph):
        calls.append(graph.number_of_nodes())
        if len(calls) == 1:  # level 0: one big community
            return [set(graph.nodes)]
        return [  # level 1: the two triangles
            {"A1", "A2", "A3"},
            {"B1", "B2", "B3"},
        ]

    reports = detect_communities(
        idx, max_community_size=4, min_community_size=2, partition_fn=fake_partition
    )
    level0 = [r for r in reports if r.level == 0]
    level1 = [r for r in reports if r.level == 1]
    assert len(level0) == 1 and set(level0[0].entity_ids) == all_nodes
    assert sorted(tuple(r.entity_ids) for r in level1) == [
        ("A1", "A2", "A3"),
        ("B1", "B2", "B3"),
    ]
    for r in level1:
        assert r.community_id.startswith(level0[0].community_id + "/")
