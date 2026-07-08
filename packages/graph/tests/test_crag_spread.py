"""CRAG spread penalty + semantic judge blend (v3.2 additions)."""

from __future__ import annotations

import pytest
from graphrag_graph.crag import CragScorer


def _hits(scores: list[float]) -> list[dict]:
    return [{"content": f"c{i}", "score": s, "rerank_score": s} for i, s in enumerate(scores)]


def test_flat_high_scores_are_damped_by_spread_penalty():
    flat = _hits([0.72, 0.72, 0.72, 0.72, 0.72])
    baseline = CragScorer().score("q", flat)
    penalized = CragScorer(spread_penalty=0.5, min_spread=0.05).score("q", flat)
    # A perfectly flat distribution loses ranking signal → score is damped.
    assert penalized.score < baseline.score
    assert penalized.detail["flatness"] == pytest.approx(1.0)


def test_varied_scores_are_not_penalized():
    varied = _hits([0.95, 0.7, 0.5, 0.3, 0.1])
    baseline = CragScorer().score("q", varied)
    penalized = CragScorer(spread_penalty=0.5, min_spread=0.05).score("q", varied)
    assert penalized.score == pytest.approx(baseline.score)
    assert penalized.detail["flatness"] == pytest.approx(0.0)


def test_semantic_judge_blends_into_final_score():
    hits = _hits([0.9, 0.9, 0.9])
    # judge says the evidence is actually irrelevant despite high scores
    scorer = CragScorer(judge=lambda q, contents: 0.0, judge_weight=1.0)
    result = scorer.score("q", hits)
    assert result.score == pytest.approx(0.0)
    assert result.decision == "fallback"
    assert result.detail["semantic"] == pytest.approx(0.0)


def test_judge_failure_never_breaks_routing():
    def broken_judge(q, contents):
        raise RuntimeError("judge down")

    hits = _hits([0.9, 0.9, 0.9])
    result = CragScorer(judge=broken_judge, judge_weight=1.0).score("q", hits)
    # falls back to the statistical score; still routes
    assert result.decision in {"use", "rewrite", "fallback"}
    assert result.detail["semantic"] is None


def test_spread_penalty_bounds_validated():
    with pytest.raises(ValueError):
        CragScorer(spread_penalty=1.5)
    with pytest.raises(ValueError):
        CragScorer(judge_weight=-0.1)
