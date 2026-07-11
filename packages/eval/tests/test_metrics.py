"""Custom Agentic-RAG metric tests."""

from __future__ import annotations

import pytest
from graphrag_eval.metrics import (
    EXPECTED_NODES,
    answer_point_recall,
    audit_coverage,
    citation_precision,
    citation_recall,
    citation_validity,
    crag_fix_rate,
    retrieval_recall_at_k,
    tool_call_necessity,
    trace_completeness,
)

# ---- trace_completeness ----------------------------------------------


def test_trace_completeness_full_happy_path():
    audit = [{"node": n} for n in EXPECTED_NODES]
    assert trace_completeness(audit) == 1.0


def test_trace_completeness_fallback_substitutes_generator():
    audit = [
        {"node": "planner"},
        {"node": "retriever"},
        {"node": "evaluator"},
        {"node": "fallback"},
        {"node": "auditor"},
    ]
    assert trace_completeness(audit) == 1.0


def test_trace_completeness_requires_generator_on_answer_path():
    audit = [
        {"node": "planner"},
        {"node": "retriever"},
        {"node": "evaluator"},
        {"node": "auditor"},
    ]
    assert trace_completeness(audit) < 1.0


def test_trace_completeness_missing_node_penalised():
    audit = [{"node": "planner"}, {"node": "retriever"}]
    score = trace_completeness(audit)
    assert 0 < score < 1


# ---- tool_call_necessity ---------------------------------------------


def test_tool_call_necessity_all_cited():
    tools = [{"name": "vector"}, {"name": "bm25"}]
    audit = [{"detail": {"cited_tools": ["vector", "bm25"]}}]
    assert tool_call_necessity(tools, audit) == 1.0


def test_tool_call_necessity_half_cited():
    tools = [{"name": "vector"}, {"name": "bm25"}]
    audit = [{"detail": {"cited_tools": ["vector"]}}]
    assert tool_call_necessity(tools, audit) == 0.5


def test_tool_call_necessity_no_tools_is_one():
    assert tool_call_necessity([], [{"detail": {}}]) == 1.0


def test_tool_call_necessity_accepts_canonical_tool_field():
    tools = [{"tool": "retrieve_vector"}, {"tool": "retrieve_bm25"}]
    audit = [{"detail": {"cited_tools": ["retrieve_vector"]}}]
    assert tool_call_necessity(tools, audit) == 0.5


# ---- audit_coverage --------------------------------------------------


def test_audit_coverage_full():
    audit = [{"node": "planner"}, {"node": "evaluator"}]
    decisions = [{"node": "planner"}, {"node": "evaluator"}]
    assert audit_coverage(audit, decisions) == 1.0


def test_audit_coverage_partial():
    audit = [{"node": "planner"}]
    decisions = [{"node": "planner"}, {"node": "evaluator"}]
    assert audit_coverage(audit, decisions) == 0.5


def test_audit_coverage_uses_required_nodes_without_decisions():
    assert audit_coverage([], [], required_nodes=("planner", "retriever")) == 0.0
    assert audit_coverage([{"node": "planner"}], [], required_nodes=("planner", "retriever")) == 0.5


# ---- crag_fix_rate ---------------------------------------------------


def test_crag_fix_rate_no_rewrites_returns_zero():
    runs = [{"rewrite_iterations": 0, "final_decision": "use"}] * 5
    assert crag_fix_rate(runs) == 0.0


def test_crag_fix_rate_perfect_recovery():
    runs = [
        {"rewrite_iterations": 1, "final_decision": "use"},
        {"rewrite_iterations": 2, "final_decision": "use"},
    ]
    assert crag_fix_rate(runs) == 1.0


def test_crag_fix_rate_partial_recovery():
    runs = [
        {"rewrite_iterations": 1, "final_decision": "use"},
        {"rewrite_iterations": 2, "final_decision": "fallback"},
        {"rewrite_iterations": 1, "final_decision": "use"},
        {"rewrite_iterations": 0, "final_decision": "use"},  # not counted
    ]
    assert crag_fix_rate(runs) == pytest.approx(2 / 3)


def test_crag_fix_rate_accepts_canonical_graph_state_fields():
    runs = [
        {"rewrite_iteration": 1, "crag_decision": "use"},
        {"rewrite_iteration": 2, "crag_decision": "fallback"},
    ]
    assert crag_fix_rate(runs) == 0.5


# ---- deterministic gold citation metrics ---------------------------


def test_gold_evidence_metrics_penalize_missing_and_extra_citations():
    gold = ["c1", "c2"]
    cited = ["c1", "noise"]
    retrieved = ["noise", "c1", "c2"]

    assert retrieval_recall_at_k(retrieved, gold, k=2) == 0.5
    assert citation_precision(cited, gold) == 0.5
    assert citation_recall(cited, gold) == 0.5


def test_answer_point_recall_checks_required_and_forbidden_behavior():
    answer = "BGE-Reranker-v2-m3 was released in 2024."
    assert answer_point_recall(answer, ["BGE-Reranker-v2-m3", "2024"]) == 1.0
    assert answer_point_recall(answer, ["BGE-Reranker-v2-m3", "2022"]) == 0.5
    assert answer_point_recall(answer, ["2024"], forbidden_points=["2024"]) == 0.0


def test_citation_validity_requires_citations_and_claims_to_be_retrieved():
    assert (
        citation_validity(
            cited_chunk_ids=["c1"],
            retrieved_chunk_ids=["c1", "c2"],
            claims=[{"text": "ok", "evidence_ids": ["c1"]}],
        )
        == 1.0
    )
    assert (
        citation_validity(
            cited_chunk_ids=["c1"],
            retrieved_chunk_ids=["c1", "c2"],
            claims=[{"text": "ghost", "evidence_ids": ["ghost"]}],
        )
        == 0.0
    )
