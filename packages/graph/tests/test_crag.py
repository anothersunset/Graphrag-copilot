"""CragScorer boundary + decision-mapping tests."""

from __future__ import annotations

import pytest
from graphrag_graph.crag import CragScorer


def _hit(score=0.5, rerank=None, content="x"):
    return {"content": content, "score": score, "rerank_score": rerank}


def test_no_hits_fallback():
    r = CragScorer().score("q", [])
    assert r.decision == "fallback"
    assert r.score == 0.0


def test_high_rerank_scores_route_use():
    hits = [_hit(rerank=0.95) for _ in range(5)]
    r = CragScorer().score("q", hits)
    assert r.decision == "use"
    assert r.score >= 0.7


def test_medium_scores_route_rewrite():
    hits = [_hit(rerank=0.5) for _ in range(5)]
    r = CragScorer().score("q", hits)
    assert r.decision == "rewrite"
    assert 0.3 <= r.score < 0.7


def test_low_scores_route_fallback():
    hits = [_hit(rerank=0.05) for _ in range(5)]
    r = CragScorer().score("q", hits)
    assert r.decision == "fallback"
    assert r.score < 0.3


def test_injected_scorer_overrides_rerank():
    hits = [_hit(rerank=0.0) for _ in range(3)]
    scorer = CragScorer(scorer=lambda q, contents: [0.9, 0.9, 0.9])
    r = scorer.score("q", hits)
    # injected scorer pushes relevance up, but coverage still depends on rerank/score
    assert r.relevance == pytest.approx(0.9)


def test_invalid_thresholds_reject():
    with pytest.raises(ValueError):
        CragScorer(use_threshold=0.3, rewrite_threshold=0.5)
    with pytest.raises(ValueError):
        CragScorer(alpha=1.5)
