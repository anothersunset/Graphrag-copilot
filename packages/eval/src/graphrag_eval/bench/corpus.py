"""Fixed bilingual corpus for the provenance bench.

The corpus is intentionally tiny (12 chunks, 6 zh + 6 en) and the graph
triples are hand-authored so the bench stays:

* deterministic — no embedding model, no LLM, no DB;
* fast — the whole bench finishes well under a second in CI;
* explainable — every claim a reference run produces lands on a chunk
  you can read on screen.

If you grow the corpus, keep chunk ids monotonic (``c01``, ``c02``,…)
because the reference orchestrator uses chunk id as a deterministic
tiebreaker when overlap scores tie.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Language = Literal["en", "zh"]


@dataclass(frozen=True)
class CorpusChunk:
    id: str
    text: str
    language: Language
    entities: tuple[str, ...] = field(default_factory=tuple)


CORPUS: tuple[CorpusChunk, ...] = (
    CorpusChunk(
        id="c01",
        text="Neo4j is a property graph database that uses Cypher as its query language.",
        language="en",
        entities=("Neo4j", "Cypher"),
    ),
    CorpusChunk(
        id="c02",
        text="GraphRAG is a retrieval architecture that combines vector search with knowledge graph traversal.",
        language="en",
        entities=("GraphRAG",),
    ),
    CorpusChunk(
        id="c03",
        text="GraphRAG uses Neo4j as its default graph backend in many open-source implementations.",
        language="en",
        entities=("GraphRAG", "Neo4j"),
    ),
    CorpusChunk(
        id="c04",
        text="BGE-Reranker-v2-m3 was released by BAAI in 2024 and supports multilingual reranking.",
        language="en",
        entities=("BGE-Reranker-v2-m3", "BAAI"),
    ),
    CorpusChunk(
        id="c05",
        text="The Corrective Retrieval Augmented Generation paper was published at ACL 2024.",
        language="en",
        entities=("CRAG", "ACL"),
    ),
    CorpusChunk(
        id="c06",
        text="Self-RAG augments a base model with on-the-fly retrieval and reflection tokens to gate generation.",
        language="en",
        entities=("Self-RAG",),
    ),
    CorpusChunk(
        id="c07",
        text="Neo4j 是一种原生存储的属性图数据库，官方查询语言为 Cypher。",
        language="zh",
        entities=("Neo4j", "Cypher"),
    ),
    CorpusChunk(
        id="c08",
        text="GraphRAG 是一种将向量检索与知识图谱结合的检索增强生成架构。",
        language="zh",
        entities=("GraphRAG",),
    ),
    CorpusChunk(
        id="c09",
        text="GraphRAG 默认使用 Neo4j 作为下游图存储后端，并通过 Cypher 查询实现多跳推理。",
        language="zh",
        entities=("GraphRAG", "Neo4j", "Cypher"),
    ),
    CorpusChunk(
        id="c10",
        text="GraphRAG 在中文企业知识库场景下相比纯向量检索能将多跳问答准确率提升约 15 个百分点。",
        language="zh",
        entities=("GraphRAG",),
    ),
    CorpusChunk(
        id="c11",
        text="BGE-Reranker-v2-m3 由智源 BAAI 在 2024 年发布，是一个支持中英双语的多语言重排序模型。",
        language="zh",
        entities=("BGE-Reranker-v2-m3", "BAAI"),
    ),
    CorpusChunk(
        id="c12",
        text="Anthropic 在 2024 年提出的 Contextual Retrieval 通过为每个分块附加上下文摘要降低检索失败率约 49%。",
        language="zh",
        entities=("Anthropic", "Contextual Retrieval"),
    ),
)

# Hand-authored 1-hop relations used to build GraphPaths in the reference
# orchestrator. Triples are (head, relation, tail).
GRAPH_TRIPLES: tuple[tuple[str, str, str], ...] = (
    ("Neo4j", "query_language", "Cypher"),
    ("GraphRAG", "graph_backend", "Neo4j"),
    ("GraphRAG", "query_language", "Cypher"),
    ("BGE-Reranker-v2-m3", "released_by", "BAAI"),
    ("CRAG", "published_at", "ACL"),
    ("Anthropic", "proposed", "Contextual Retrieval"),
)
