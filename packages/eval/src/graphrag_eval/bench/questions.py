"""Gold questions and adversarial distractor cases for the bench.

Questions are intentionally a mix of:

* **factual** — single chunk lookup;
* **multi-hop** — needs two chunks to combine;
* **numeric** — contains a number that's easy to flip in a distractor;
* **definition** — short definitional sentences;

in both English and Chinese. The reference orchestrator clears every
category; this gives plug-in orchestrators a meaningful spread.

The adversarial cases reuse chunks from ``corpus.py`` and lean on
``graphrag_eval.adversarial.build_distractor`` so the swap is auditable
in the report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from graphrag_eval.adversarial import DistractorCase, build_distractor

Language = Literal["en", "zh"]
Category = Literal["factual", "multi_hop", "numeric", "definition"]


@dataclass(frozen=True)
class BenchQuestion:
    id: str
    question: str
    language: Language
    category: Category
    gold_answer: str
    gold_chunk_ids: tuple[str, ...] = field(default_factory=tuple)


GOLD_QUESTIONS: tuple[BenchQuestion, ...] = (
    BenchQuestion(
        id="q01-en-factual",
        question="Which query language does Neo4j use?",
        language="en",
        category="factual",
        gold_answer="Neo4j uses Cypher as its query language.",
        gold_chunk_ids=("c01",),
    ),
    BenchQuestion(
        id="q02-en-multi-hop",
        question="Which query language does GraphRAG's default graph backend support?",
        language="en",
        category="multi_hop",
        gold_answer="GraphRAG's default backend Neo4j supports Cypher.",
        gold_chunk_ids=("c03", "c01"),
    ),
    BenchQuestion(
        id="q03-en-numeric",
        question="In what year was BGE-Reranker-v2-m3 released?",
        language="en",
        category="numeric",
        gold_answer="BGE-Reranker-v2-m3 was released by BAAI in 2024.",
        gold_chunk_ids=("c04",),
    ),
    BenchQuestion(
        id="q04-en-definition",
        question="What is Self-RAG?",
        language="en",
        category="definition",
        gold_answer="Self-RAG augments a base model with on-the-fly retrieval and reflection tokens to gate generation.",
        gold_chunk_ids=("c06",),
    ),
    BenchQuestion(
        id="q05-zh-factual",
        question="Neo4j 的官方查询语言是什么？",
        language="zh",
        category="factual",
        gold_answer="Neo4j 的官方查询语言是 Cypher。",
        gold_chunk_ids=("c07",),
    ),
    BenchQuestion(
        id="q06-zh-multi-hop",
        question="GraphRAG 默认使用哪个图数据库作为后端，它的查询语言是什么？",
        language="zh",
        category="multi_hop",
        gold_answer="GraphRAG 默认使用 Neo4j 作为图存储后端，查询语言为 Cypher。",
        gold_chunk_ids=("c09", "c07"),
    ),
    BenchQuestion(
        id="q07-zh-numeric",
        question="GraphRAG 在中文企业知识库上能带来多少个百分点的多跳问答准确率提升？",
        language="zh",
        category="numeric",
        gold_answer="GraphRAG 在中文企业知识库场景下能将多跳问答准确率提升约 15 个百分点。",
        gold_chunk_ids=("c10",),
    ),
    BenchQuestion(
        id="q08-zh-definition",
        question="Contextual Retrieval 是谁提出的，能够降低检索失败率多少？",
        language="zh",
        category="definition",
        gold_answer="Anthropic 在 2024 年提出的 Contextual Retrieval 可将检索失败率降低约 49%。",
        gold_chunk_ids=("c12",),
    ),
)


_ADV_GOLD: dict[str, dict] = {
    "c01": {"chunk_id": "c01", "content": "Neo4j is a property graph database that uses Cypher as its query language.", "source": "bm25"},
    "c02": {"chunk_id": "c02", "content": "GraphRAG is a retrieval architecture that combines vector search with knowledge graph traversal.", "source": "bm25"},
    "c03": {"chunk_id": "c03", "content": "GraphRAG uses Neo4j as its default graph backend in many open-source implementations.", "source": "bm25"},
    "c04": {"chunk_id": "c04", "content": "BGE-Reranker-v2-m3 was released by BAAI in 2024 and supports multilingual reranking.", "source": "bm25"},
    "c05": {"chunk_id": "c05", "content": "The Corrective Retrieval Augmented Generation paper was published at ACL 2024.", "source": "bm25"},
    "c10": {"chunk_id": "c10", "content": "GraphRAG 在中文企业知识库场景下相比纯向量检索能将多跳问答准确率提升约 15 个百分点。", "source": "bm25"},
    "c12": {"chunk_id": "c12", "content": "Anthropic 在 2024 年提出的 Contextual Retrieval 通过为每个分块附加上下文摘要降低检索失败率约 49%。", "source": "bm25"},
}


def _adv(
    case_id: str,
    question: str,
    gold_answer: str,
    gold_ids: list[str],
    swap: tuple[str, str],
) -> DistractorCase:
    gold_chunks = [_ADV_GOLD[g] for g in gold_ids]
    distractor = build_distractor(
        case_id=case_id,
        gold_chunk=gold_chunks[0],
        swap=swap,
    )
    return DistractorCase(
        case_id=case_id,
        question=question,
        gold_answer=gold_answer,
        gold_chunks=gold_chunks,
        distractor_chunk=distractor,
        expected_cited_ids=list(gold_ids),
    )


BENCH_DISTRACTORS: tuple[DistractorCase, ...] = (
    _adv(
        case_id="bd01-neo4j-query-lang",
        question="Neo4j is a graph database. Which query language does Cypher refer to in Neo4j?",
        gold_answer="Neo4j is a property graph database that uses Cypher as its query language.",
        gold_ids=["c01"],
        swap=("Cypher", "SQL"),
    ),
    _adv(
        case_id="bd02-graphrag-backend",
        question="Which graph database does GraphRAG use as its default Neo4j-style backend?",
        gold_answer="GraphRAG uses Neo4j as its default graph backend in many open-source implementations.",
        gold_ids=["c03", "c02"],
        swap=("Neo4j", "MongoDB"),
    ),
    _adv(
        case_id="bd03-bge-year",
        question="BGE-Reranker-v2-m3 multilingual reranking release year by BAAI?",
        gold_answer="BGE-Reranker-v2-m3 was released by BAAI in 2024 and supports multilingual reranking.",
        gold_ids=["c04"],
        swap=("2024", "2022"),
    ),
    _adv(
        case_id="bd04-crag-venue",
        question="At which venue was the Corrective Retrieval Augmented Generation paper published in 2024?",
        gold_answer="The Corrective Retrieval Augmented Generation paper was published at ACL 2024.",
        gold_ids=["c05"],
        swap=("ACL", "EMNLP"),
    ),
    _adv(
        case_id="bd05-zh-graphrag-gain",
        question="GraphRAG 在中文企业知识库上多跳问答准确率提升约多少个百分点？",
        gold_answer="GraphRAG 在中文企业知识库场景下能将多跳问答准确率提升约 15 个百分点。",
        gold_ids=["c10"],
        swap=("15 个百分点", "5 个百分点"),
    ),
    _adv(
        case_id="bd06-zh-contextual",
        question="Contextual Retrieval 是哪家公司在 2024 年提出的检索分块增强方法？",
        gold_answer="Anthropic 在 2024 年提出的 Contextual Retrieval 可将检索失败率降低约 49%。",
        gold_ids=["c12"],
        swap=("Anthropic", "Cohere"),
    ),
)
