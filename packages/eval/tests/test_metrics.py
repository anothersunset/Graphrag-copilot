"""Custom Agentic-RAG metric tests."""
from __future__ import annotations

import pytest

from graphrag_eval.metrics import (
    EXPECTED_NODES,
    audit_coverage,
    crag_fix_rate,
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


# ---- audit_coverage --------------------------------------------------

def test_audit_coverage_full():
    audit = [{"node": "planner"}, {"node": "evaluator"}]
    decisions = [{"node": "planner"}, {"node": "evaluator"}]
    assert audit_coverage(audit, decisions) == 1.0


def test_audit_coverage_partial():
    audit = [{"node": "planner"}]
    decisions = [{"node": "planner"}, {"node": "evaluator"}]
    assert audit_coverage(audit, decisions) == 0.5


def test_audit_coverage_no_decisions_is_one():
    assert audit_coverage([], []) == 1.0


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
        {"rewrite_iterations": 0, "final_decision": "use"},   # not counted
    ]
    assert crag_fix_rate(runs) == pytest.approx(2 / 3)
