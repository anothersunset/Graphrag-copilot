"""Provenance Sufficiency metric tests."""

from __future__ import annotations

from graphrag_eval.metrics import provenance_sufficiency_score
from graphrag_eval.provenance import provenance_sufficiency

CONTEXTS = {
    "c1": "GraphRAG combines vector retrieval and knowledge graph traversal for multi-hop reasoning.",
    "c2": "Neo4j is a graph database queried using the Cypher language.",
    "c3": "BM25 is a sparse retrieval scoring function.",
}


def test_full_provenance_passes_when_every_claim_supported():
    answer = (
        "GraphRAG combines vector retrieval and knowledge graph traversal."
        " Neo4j is a graph database queried using Cypher."
    )
    claims = [
        {
            "text": "GraphRAG combines vector retrieval and knowledge graph traversal.",
            "evidence_ids": ["c1"],
        },
        {"text": "Neo4j is a graph database queried using Cypher.", "evidence_ids": ["c2"]},
    ]
    report = provenance_sufficiency(
        answer=answer,
        claims=claims,
        cited_chunk_ids=["c1", "c2"],
        chunk_contents=CONTEXTS,
    )
    assert report.sentence_recall == 1.0
    assert report.score >= 0.9
    assert report.missing_evidence_claims == []


def test_missing_evidence_drops_recall():
    answer = "GraphRAG uses BM25 for sparse retrieval. The moon is made of cheese."
    claims = [
        {"text": "GraphRAG uses BM25 for sparse retrieval.", "evidence_ids": ["c3"]},
        {"text": "The moon is made of cheese.", "evidence_ids": []},
    ]
    report = provenance_sufficiency(
        answer=answer,
        claims=claims,
        cited_chunk_ids=["c3"],
        chunk_contents=CONTEXTS,
    )
    assert report.sentence_recall == 0.5
    assert "The moon is made of cheese." in report.missing_evidence_claims


def test_low_coverage_penalizes_score():
    answer = (
        "GraphRAG combines vector retrieval and knowledge graph traversal"
        " and additionally performs adversarial hallucination defense and"
        " symbolic reasoning over typed entity hierarchies."
    )
    claims = [
        {
            "text": "GraphRAG combines vector retrieval and knowledge graph traversal.",
            "evidence_ids": ["c1"],
        },
    ]
    report = provenance_sufficiency(
        answer=answer,
        claims=claims,
        cited_chunk_ids=["c1"],
        chunk_contents=CONTEXTS,
        coverage_floor=0.9,
    )
    # recall is 1.0 but coverage is well below the floor
    assert report.coverage < 0.9
    assert report.score < 1.0


def test_injectable_entailer_can_rescue_low_overlap_claim():
    answer = "GraphRAG 支持多跳推理。"
    claims = [{"text": "GraphRAG 支持多跳推理。", "evidence_ids": ["c1"]}]
    # Without entailer the zh sentence has ≤ 1 token overlap with the en context, so it fails.
    no_ent = provenance_sufficiency(
        answer=answer,
        claims=claims,
        cited_chunk_ids=["c1"],
        chunk_contents=CONTEXTS,
    )
    assert no_ent.sentence_recall == 0.0

    # With a hand-rolled entailer that returns 0.9, the claim is supported.
    def yes_entailer(*, premise: str, hypothesis: str) -> float:
        return 0.9

    with_ent = provenance_sufficiency(
        answer=answer,
        claims=claims,
        cited_chunk_ids=["c1"],
        chunk_contents=CONTEXTS,
        entailer=yes_entailer,
        entailment_floor=0.4,
    )
    assert with_ent.sentence_recall == 1.0


def test_empty_answer_returns_zero_recall():
    report = provenance_sufficiency(
        answer="",
        claims=[],
        cited_chunk_ids=[],
        chunk_contents={},
    )
    assert report.sentence_recall == 0.0
    assert report.coverage == 0.0


def test_metrics_wrapper_returns_scalar():
    score = provenance_sufficiency_score(
        answer="GraphRAG uses BM25.",
        claims=[{"text": "GraphRAG uses BM25.", "evidence_ids": ["c3"]}],
        cited_chunk_ids=["c3"],
        chunk_contents=CONTEXTS,
    )
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_numeric_date_percent_and_version_conflicts_are_not_supported():
    cases = [
        ("The model was released in 2022.", "The model was released in 2024."),
        ("Recall improved by 15%.", "Recall improved by 5%."),
        ("The supported runtime is Python 3.11.", "The supported runtime is Python 3.12."),
        ("The release is v2.3.1.", "The release is v2.4.0."),
    ]
    for answer, evidence in cases:
        report = provenance_sufficiency(
            answer=answer,
            claims=[{"text": answer, "evidence_ids": ["c"]}],
            cited_chunk_ids=["c"],
            chunk_contents={"c": evidence},
        )
        assert report.sentence_recall == 0.0, (answer, evidence, report.to_dict())


def test_obvious_negation_conflict_is_not_supported():
    report = provenance_sufficiency(
        answer="Neo4j is available.",
        claims=[{"text": "Neo4j is available.", "evidence_ids": ["c"]}],
        cited_chunk_ids=["c"],
        chunk_contents={"c": "Neo4j is not available."},
    )
    assert report.sentence_recall == 0.0


def test_explicitly_unsupported_claim_cannot_score_as_sufficient():
    report = provenance_sufficiency(
        answer="GraphRAG uses BM25.",
        claims=[
            {
                "text": "GraphRAG uses BM25.",
                "evidence_ids": ["c3"],
                "support": "unsupported",
            }
        ],
        cited_chunk_ids=["c3"],
        chunk_contents=CONTEXTS,
    )
    assert report.sentence_recall == 0.0
