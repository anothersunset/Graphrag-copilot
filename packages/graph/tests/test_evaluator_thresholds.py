"""Evaluator routes correctly across the locked CRAG thresholds."""

from __future__ import annotations

from graphrag_graph.config import CragThresholds


def test_use_at_07_and_above():
    t = CragThresholds()
    assert t.decide(0.70) == "use"
    assert t.decide(0.95) == "use"
    assert t.decide(1.0) == "use"


def test_rewrite_between_03_and_07():
    t = CragThresholds()
    assert t.decide(0.30) == "rewrite"
    assert t.decide(0.50) == "rewrite"
    assert t.decide(0.6999) == "rewrite"


def test_fallback_below_03():
    t = CragThresholds()
    assert t.decide(0.0) == "fallback"
    assert t.decide(0.29) == "fallback"


def test_thresholds_are_locked_at_v31_values():
    t = CragThresholds()
    assert t.use == 0.7
    assert t.rewrite_low == 0.3
