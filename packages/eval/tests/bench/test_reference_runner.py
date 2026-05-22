"""Tests for the deterministic reference orchestrator + adversarial adapter."""
from __future__ import annotations

import pytest

from graphrag_eval.bench import (
    BENCH_DISTRACTORS,
    GOLD_QUESTIONS,
    adversarial_orchestrator_adapter,
    reference_orchestrator,
)


def test_reference_orchestrator_returns_required_keys():
    out = reference_orchestrator(GOLD_QUESTIONS[0].question)
    for key in (
        "answer",
        "claims",
        "cited_chunk_ids",
        "evidence_pack",
        "query_history",
        "verdict",
    ):
        assert key in out, f"missing key {key}"
    assert out["answer"], "empty answer"
    assert out["cited_chunk_ids"], "empty cited_chunk_ids"


def test_reference_orchestrator_is_deterministic():
    a = reference_orchestrator(GOLD_QUESTIONS[0].question)
    b = reference_orchestrator(GOLD_QUESTIONS[0].question)
    assert a == b


@pytest.mark.parametrize("q", list(GOLD_QUESTIONS), ids=[q.id for q in GOLD_QUESTIONS])
def test_reference_top_cited_is_in_gold(q):
    out = reference_orchestrator(q.question)
    assert out["cited_chunk_ids"], q.id
    assert out["cited_chunk_ids"][0] in q.gold_chunk_ids, (
        f"{q.id}: top cited {out['cited_chunk_ids'][0]} not in {q.gold_chunk_ids}"
    )


def test_reference_emits_verdict_supported_for_gold():
    for q in GOLD_QUESTIONS:
        out = reference_orchestrator(q.question)
        assert out["verdict"] == "supported", q.id


def test_adversarial_adapter_visits_distractor_node():
    case = BENCH_DISTRACTORS[0]
    corpus = list(case.gold_chunks) + [case.distractor_chunk]
    out = adversarial_orchestrator_adapter(case.question, corpus)
    visited_ids = {n["id"] for n in out["evidence_pack"]["visited_nodes"]}
    assert case.distractor_chunk["node_id"] in visited_ids


def test_adversarial_adapter_does_not_cite_distractor():
    for case in BENCH_DISTRACTORS:
        corpus = list(case.gold_chunks) + [case.distractor_chunk]
        out = adversarial_orchestrator_adapter(case.question, corpus)
        assert case.distractor_chunk["chunk_id"] not in out["cited_chunk_ids"], (
            f"{case.case_id}: distractor was cited"
        )


def test_adversarial_adapter_claims_never_bind_distractor():
    for case in BENCH_DISTRACTORS:
        corpus = list(case.gold_chunks) + [case.distractor_chunk]
        out = adversarial_orchestrator_adapter(case.question, corpus)
        distractor_id = case.distractor_chunk["chunk_id"]
        for claim in out["claims"]:
            assert distractor_id not in claim.get("evidence_ids", []), (
                f"{case.case_id}: claim cited distractor"
            )
