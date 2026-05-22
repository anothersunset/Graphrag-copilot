"""Conditional edge router unit tests."""

from __future__ import annotations

from graphrag_graph.edges import route_after_evaluator


def test_use_routes_to_generator():
    assert route_after_evaluator({"crag_decision": "use"}) == "use"


def test_fallback_routes_to_fallback():
    assert route_after_evaluator({"crag_decision": "fallback"}) == "fallback"


def test_rewrite_under_cap_routes_to_rewriter():
    assert route_after_evaluator({"crag_decision": "rewrite", "rewrite_iteration": 0}) == "rewrite"
    assert route_after_evaluator({"crag_decision": "rewrite", "rewrite_iteration": 1}) == "rewrite"


def test_rewrite_at_cap_falls_back():
    assert route_after_evaluator({"crag_decision": "rewrite", "rewrite_iteration": 2}) == "fallback"
    assert route_after_evaluator({"crag_decision": "rewrite", "rewrite_iteration": 5}) == "fallback"


def test_missing_decision_defaults_to_fallback():
    assert route_after_evaluator({}) == "fallback"
