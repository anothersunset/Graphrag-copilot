"""Index persistence: save → load must reproduce retrieval behaviour."""

from __future__ import annotations

import pytest
from graphrag_kg import (
    Chunk,
    GraphRAGIndex,
    build_index,
    load_index,
    save_index,
)

CORPUS = [
    Chunk("c1", "GraphRAG 使用 Neo4j 存储知识图谱。Neo4j 通过 Cypher 查询语言访问。"),
    Chunk("c2", "GraphRAG 结合向量检索与图谱检索。向量检索依赖 embedding 模型。"),
    Chunk("c3", "BM25 是稀疏检索算法。BM25 依赖关键词匹配。jieba 负责中文分词。"),
    Chunk("c4", "社区检测使用 Louvain 算法。Louvain 通过模块度优化划分社区。"),
]


def _stats(index: GraphRAGIndex) -> dict:
    return {
        **index.stats(),
        "chunk_texts": len(index.chunk_texts),
        "summary_heads": [r.summary[:30] for r in index.communities],
    }


def test_roundtrip_preserves_index_stats(tmp_path):
    original = build_index(CORPUS)
    path = save_index(original, tmp_path / "index.json")
    assert path.exists()

    restored = load_index(path)
    assert _stats(restored) == _stats(original)


async def test_roundtrip_preserves_ppr_retrieval(tmp_path):
    original = build_index(CORPUS)
    path = save_index(original, tmp_path / "index.json")
    restored = load_index(path)

    q = "Neo4j 用什么查询语言?"
    hits_orig = await original.ppr_retriever().aretrieve(q, top_k=5)
    hits_restored = await restored.ppr_retriever().aretrieve(q, top_k=5)
    assert hits_orig and hits_restored
    assert [h["chunk_id"] for h in hits_restored] == [h["chunk_id"] for h in hits_orig]
    assert [h["score"] for h in hits_restored] == [h["score"] for h in hits_orig]


def test_roundtrip_preserves_alias_resolution(tmp_path):
    original = build_index(CORPUS)
    save_index(original, tmp_path / "index.json")
    restored = load_index(tmp_path / "index.json")

    # case/whitespace-normalized surface forms resolve identically
    for surface in ("neo4j", "Neo4j ", "graphrag"):
        assert restored.graph.resolve_name(surface) == original.graph.resolve_name(surface)


async def test_roundtrip_preserves_community_retrieval(tmp_path):
    from graphrag_retrieval.community import CommunityRetriever

    original = build_index(CORPUS)
    save_index(original, tmp_path / "index.json")
    restored = load_index(tmp_path / "index.json")

    q = "总结主要主题"
    hits_o = await CommunityRetriever(original.communities).aretrieve(q, top_k=3)
    hits_r = await CommunityRetriever(restored.communities).aretrieve(q, top_k=3)
    assert [h["chunk_id"] for h in hits_r] == [h["chunk_id"] for h in hits_o]


def test_load_rejects_unknown_version(tmp_path):
    path = tmp_path / "index.json"
    path.write_text('{"version": 999, "graph": {}, "communities": [], "chunk_texts": {}}',
                    encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_index(path)


def test_saved_file_is_valid_json_with_no_sets(tmp_path):
    import json

    original = build_index(CORPUS)
    path = save_index(original, tmp_path / "index.json")
    payload = json.loads(path.read_text(encoding="utf-8"))  # would fail on sets
    assert payload["version"] == 1
    for link in payload["graph"]["links"]:
        assert isinstance(link["types"], list)
