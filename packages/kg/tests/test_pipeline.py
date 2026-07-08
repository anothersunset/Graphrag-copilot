"""End-to-end index pipeline: chunks → graph + communities → retrievers."""

from __future__ import annotations

from graphrag_kg import build_index
from graphrag_kg.pipeline import Chunk


def _corpus() -> list[Chunk]:
    return [
        Chunk("c1", "GraphRAG 使用 Neo4j 存储知识图谱。Neo4j 通过 Cypher 查询。"),
        Chunk("c2", "GraphRAG 结合向量检索与图检索。向量检索使用 embedding。"),
        Chunk("c3", "BM25 是稀疏检索算法。BM25 依赖关键词匹配。jieba 做中文分词。"),
    ]


def test_offline_pipeline_builds_graph_and_communities():
    index = build_index(_corpus())  # no LLM → co-occurrence + template
    stats = index.stats()
    assert stats["nodes"] > 0
    assert stats["edges"] > 0
    assert stats["communities"] >= 1
    # every community has a summary (template path)
    assert all(c.summary for c in index.communities)


async def test_pipeline_ppr_retriever_answers_local_query():
    index = build_index(_corpus())
    retriever = index.ppr_retriever()
    hits = await retriever.aretrieve("GraphRAG 和 Neo4j 的关系", top_k=3)
    assert hits
    assert hits[0]["chunk_id"] in {"c1", "c2"}
    assert hits[0]["content"]  # hydrated from chunk_lookup


def test_pipeline_accepts_dict_chunks():
    index = build_index([{"chunk_id": "c1", "content": "GraphRAG 使用 Neo4j。"}])
    assert index.chunk_lookup("c1") == "GraphRAG 使用 Neo4j。"


def test_pipeline_with_injected_llm_extractor():
    calls: list[str] = []

    def fake_llm(system: str, user: str) -> str:
        calls.append(user)
        if "分析专家" in system:  # community summarizer role
            return "核心主题\n这是一个关于图检索的社区。"
        if "遗漏" in user:  # gleaning pass
            return '{"entities": [], "relations": []}'
        return (  # first extraction pass
            '{"entities": [{"name": "GraphRAG", "type": "Technology"},'
            ' {"name": "Neo4j", "type": "Technology"}],'
            ' "relations": [{"source": "GraphRAG", "target": "Neo4j", "type": "USES"}]}'
        )

    index = build_index(
        [Chunk("c1", "GraphRAG uses Neo4j.")],
        llm=fake_llm,
        max_gleanings=1,
    )
    assert index.graph.resolve_name("graphrag") == "GraphRAG"
    assert calls  # llm was actually used
