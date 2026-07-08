"""Evaluator routes correctly across the tuned CRAG thresholds."""

from __future__ import annotations

from graphrag_graph.config import CragThresholds


def test_use_at_05_and_above():
    t = CragThresholds()
    assert t.decide(0.50) == "use"
    assert t.decide(0.95) == "use"
    assert t.decide(1.0) == "use"


def test_rewrite_between_02_and_05():
    t = CragThresholds()
    assert t.decide(0.20) == "rewrite"
    assert t.decide(0.35) == "rewrite"
    assert t.decide(0.4999) == "rewrite"


def test_fallback_below_02():
    t = CragThresholds()
    assert t.decide(0.0) == "fallback"
    assert t.decide(0.19) == "fallback"


def test_thresholds_match_crag_scorer_defaults():
    # CragThresholds and CragScorer must stay in sync — evaluator_node
    # passes these through, silently overriding CragScorer's own class
    # defaults whenever no explicit scorer is injected.
    t = CragThresholds()
    assert t.use == 0.5
    assert t.rewrite_low == 0.2
