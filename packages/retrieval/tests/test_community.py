"""CommunityRetriever — global-search report ranking."""

from __future__ import annotations

import asyncio

from graphrag_retrieval.community import CommunityRetriever


def _reports() -> list[dict]:
    return [
        {
            "community_id": "c0.0",
            "level": 0,
            "title": "图检索技术栈",
            "summary": "该社区围绕 GraphRAG、Neo4j、Cypher 展开知识图谱检索。",
            "entity_ids": ["GraphRAG", "Neo4j", "Cypher"],
            "chunk_ids": ["c1", "c2"],
            "rank": 0.6,
        },
        {
            "community_id": "c0.1",
            "level": 0,
            "title": "稀疏检索",
            "summary": "该社区关于 BM25 与关键词检索、中文分词。",
            "entity_ids": ["BM25", "jieba"],
            "chunk_ids": ["c3"],
            "rank": 0.2,
        },
        {
            "community_id": "c0.0/c1.0",
            "level": 1,
            "title": "子社区",
            "summary": "GraphRAG 的子话题。",
            "entity_ids": ["GraphRAG"],
            "chunk_ids": ["c1"],
            "rank": 0.1,
        },
    ]


def test_ranks_relevant_community_first():
    retriever = CommunityRetriever(_reports())
    hits = asyncio.run(retriever.aretrieve("知识图谱和 Neo4j 的整体情况", top_k=5))
    assert hits
    assert hits[0]["metadata"]["community_id"] == "c0.0"
    assert hits[0]["chunk_id"] == "community:c0.0"
    assert hits[0]["source"] == "kg"
    # provenance back to member chunks + entities is preserved
    assert hits[0]["metadata"]["member_chunk_ids"] == ["c1", "c2"]
    assert "GraphRAG" in hits[0]["visited_node_ids"]


def test_prefer_level_filters_out_sub_communities():
    retriever = CommunityRetriever(_reports(), prefer_level=0)
    hits = asyncio.run(retriever.aretrieve("GraphRAG", top_k=5))
    assert all(h["metadata"]["level"] == 0 for h in hits)


def test_structural_rank_breaks_ties_when_no_text_overlap():
    # query overlaps nothing → ranking falls back to structural rank
    retriever = CommunityRetriever(_reports(), prefer_level=0, rank_weight=1.0)
    hits = asyncio.run(retriever.aretrieve("zzz", top_k=5))
    assert hits[0]["metadata"]["community_id"] == "c0.0"  # highest rank=0.6


def test_empty_reports_returns_empty():
    assert asyncio.run(CommunityRetriever([]).aretrieve("q", top_k=5)) == []


def test_embedder_path_used_when_provided():
    class Embedder:
        def embed(self, text: str) -> list[float]:
            # crude 2-dim: [graph-ish, bm25-ish]
            g = sum(w in text for w in ("GraphRAG", "Neo4j", "知识图谱", "图检索"))
            b = sum(w in text for w in ("BM25", "分词", "稀疏"))
            return [float(g), float(b)]

    retriever = CommunityRetriever(_reports(), embedder=Embedder(), prefer_level=0)
    hits = asyncio.run(retriever.aretrieve("知识图谱 GraphRAG", top_k=5))
    assert hits[0]["metadata"]["community_id"] == "c0.0"
