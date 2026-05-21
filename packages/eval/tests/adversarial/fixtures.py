"""Six base adversarial cases covering common attack surfaces.

Each case ships a gold corpus + a distractor produced by swapping one
key token. Cases cover: definition, multi-hop relation, numeric fact,
date fact, single-hop relation (zh), and a quantitative claim (zh).
"""
from __future__ import annotations

from graphrag_eval.adversarial import DistractorCase, build_distractor


def _chunk(cid: str, content: str, node_id: str | None = None) -> dict:
    return {
        "chunk_id": cid,
        "node_id": node_id or cid,
        "source": "vector",
        "content": content,
        "score": 0.95,
        "metadata": {},
    }


def build_cases() -> list[DistractorCase]:
    cases: list[DistractorCase] = []

    # 1. Definition (en) — swap a tech name.
    gold = _chunk("def-neo4j", "Neo4j is a graph database queried by Cypher.")
    cases.append(
        DistractorCase(
            case_id="def-neo4j",
            question="How is Neo4j queried?",
            gold_answer="Neo4j is queried by Cypher.",
            gold_chunks=[gold],
            distractor_chunk=build_distractor(
                case_id="def-neo4j", gold_chunk=gold, swap=("Cypher", "SQL")
            ),
            expected_cited_ids=["def-neo4j"],
        )
    )

    # 2. Multi-hop relation (en) — swap the bridging entity.
    gold = _chunk(
        "hop-graphrag",
        "GraphRAG uses Neo4j for knowledge graph storage and Cypher for traversal.",
    )
    cases.append(
        DistractorCase(
            case_id="hop-graphrag",
            question="What does GraphRAG use for graph storage?",
            gold_answer="GraphRAG uses Neo4j for graph storage.",
            gold_chunks=[gold],
            distractor_chunk=build_distractor(
                case_id="hop-graphrag", gold_chunk=gold, swap=("Neo4j", "MongoDB")
            ),
            expected_cited_ids=["hop-graphrag"],
        )
    )

    # 3. Numeric fact (en) — swap a number.
    gold = _chunk(
        "num-bm25", "The BM25 default k1 parameter is 1.2 in most implementations."
    )
    cases.append(
        DistractorCase(
            case_id="num-bm25",
            question="What is the BM25 default k1?",
            gold_answer="1.2",
            gold_chunks=[gold],
            distractor_chunk=build_distractor(
                case_id="num-bm25", gold_chunk=gold, swap=("1.2", "2.5")
            ),
            expected_cited_ids=["num-bm25"],
        )
    )

    # 4. Date fact (en) — swap a year.
    gold = _chunk(
        "date-rrf",
        "Reciprocal Rank Fusion was proposed by Cormack et al. in 2009.",
    )
    cases.append(
        DistractorCase(
            case_id="date-rrf",
            question="When was Reciprocal Rank Fusion proposed?",
            gold_answer="2009.",
            gold_chunks=[gold],
            distractor_chunk=build_distractor(
                case_id="date-rrf", gold_chunk=gold, swap=("2009", "2019")
            ),
            expected_cited_ids=["date-rrf"],
        )
    )

    # 5. Single-hop relation (zh) — swap an algorithm name.
    gold = _chunk(
        "zh-rerank", "GraphRAG 使用 BGE-Reranker-v2-m3 作为混排模型。"
    )
    cases.append(
        DistractorCase(
            case_id="zh-rerank",
            question="GraphRAG 使用什么混排模型？",
            gold_answer="BGE-Reranker-v2-m3",
            gold_chunks=[gold],
            distractor_chunk=build_distractor(
                case_id="zh-rerank", gold_chunk=gold, swap=("BGE-Reranker-v2-m3", "Cohere-Rerank-v3")
            ),
            expected_cited_ids=["zh-rerank"],
        )
    )

    # 6. Quantitative claim (zh) — swap a percentage.
    gold = _chunk(
        "zh-coverage",
        "GraphRAG 的检索覆盖率目标是 70%，幻觉率控制在 10% 以下。",
    )
    cases.append(
        DistractorCase(
            case_id="zh-coverage",
            question="GraphRAG 的检索覆盖率目标是多少？",
            gold_answer="70%。",
            gold_chunks=[gold],
            distractor_chunk=build_distractor(
                case_id="zh-coverage", gold_chunk=gold, swap=("70%", "30%")
            ),
            expected_cited_ids=["zh-coverage"],
        )
    )

    return cases
