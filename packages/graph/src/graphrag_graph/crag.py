"""Real CRAG scorer used by the evaluator node.

CRAG (Yan et al., 2024) augments RAG by classifying retrieved evidence
into correct / ambiguous / incorrect and routing the agent accordingly.
We combine two signals:

1. **Relevance** — mean cross-encoder rerank score across the top-K hits
   (when present); falls back to the mean raw score. Cross-encoder scoring
   is dependency-injected.
2. **Coverage** — fraction of the top-K hits whose score exceeds a
   confidence floor; this captures "does the evidence set look coherent".

Final score = ``alpha * relevance + (1 - alpha) * coverage``, damped by
an always-on spread factor (see below), optionally blended with an
LLM-judge signal, and mapped to a decision via ``use_threshold`` /
``rewrite_threshold``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

CragDecision = Literal["use", "rewrite", "fallback"]
Scorer = Callable[[str, Sequence[str]], list[float]]
# Semantic judge: (query, contents) -> single relevance score in [0, 1].
# Wire an LLM-as-judge here; statistical score and semantic score are
# blended via ``judge_weight``.
Judge = Callable[[str, Sequence[str]], float]


@dataclass
class CragResult:
    score: float
    decision: CragDecision
    relevance: float
    coverage: float
    detail: dict


class CragScorer:
    """Pluggable CRAG scorer.

    Thresholds (tuned after the 50-question benchmark — see
    ``docs/devlog-2026-06-11-benchmark-evaluation.md`` §2.1/2.11; the
    original v3.1 spec values of 0.7/0.3/0.5 routed 49/50 questions to
    ``use`` and never exercised rewrite/fallback):
      * score >= 0.5        → ``use``
      * 0.2 <= score < 0.5  → ``rewrite``
      * score < 0.2         → ``fallback``
    """

    def __init__(
        self,
        *,
        scorer: Scorer | None = None,
        use_threshold: float = 0.5,
        rewrite_threshold: float = 0.2,
        coverage_floor: float = 0.3,
        alpha: float = 0.7,
        top_k: int = 5,
        spread_penalty: float = 0.0,
        min_spread: float = 0.05,
        judge: Judge | None = None,
        judge_weight: float = 0.5,
    ) -> None:
        if not (0.0 <= rewrite_threshold < use_threshold <= 1.0):
            raise ValueError("thresholds must satisfy 0 <= rewrite < use <= 1")
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        if not 0.0 <= spread_penalty <= 1.0:
            raise ValueError("spread_penalty must be in [0, 1]")
        if not 0.0 <= judge_weight <= 1.0:
            raise ValueError("judge_weight must be in [0, 1]")
        self._scorer = scorer
        self.use_threshold = use_threshold
        self.rewrite_threshold = rewrite_threshold
        self.coverage_floor = coverage_floor
        self.alpha = alpha
        self.top_k = top_k
        self.spread_penalty = spread_penalty
        self.min_spread = min_spread
        self._judge = judge
        self.judge_weight = judge_weight

    def score(self, query: str, hits: Sequence[dict]) -> CragResult:
        top = list(hits)[: self.top_k]
        if not top:
            return CragResult(
                score=0.0,
                decision="fallback",
                relevance=0.0,
                coverage=0.0,
                detail={"reason": "no_hits"},
            )

        if self._scorer is not None:
            contents = [h.get("content", "") for h in top]
            raw = self._scorer(query, contents)
            relevance = sum(raw) / len(raw) if raw else 0.0
        else:
            rerank_scores = [
                h.get("rerank_score") for h in top if h.get("rerank_score") is not None
            ]
            if rerank_scores:
                relevance = sum(rerank_scores) / len(rerank_scores)
            else:
                raw_scores = [float(h.get("score", 0.0)) for h in top]
                relevance = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0

        # Coverage: fraction of hits whose effective score >= coverage_floor.
        effective = [
            float(
                h.get("rerank_score") if h.get("rerank_score") is not None else h.get("score", 0.0)
            )
            for h in top
        ]
        coverage = sum(1 for s in effective if s >= self.coverage_floor) / len(effective)

        raw_final = self.alpha * relevance + (1.0 - self.alpha) * coverage

        # Always-on spread damping (eval-validated): a uniformly-high score
        # set means the retriever/reranker couldn't discriminate between
        # hits, which is itself a weak-evidence signal even when the mean
        # score looks good. spread=0 → 0.85x, spread>=0.5 → 1.0x (no damping).
        if len(effective) >= 2:
            score_spread = max(effective) - min(effective)
            spread_factor = min(1.0, score_spread * 2.0)
        else:
            spread_factor = 1.0
        final = raw_final * (0.85 + 0.15 * spread_factor)

        # Optional EXTRA damping (v3.2) for near-flat distributions using a
        # stricter std-dev measure; off by default (spread_penalty=0) so it
        # only kicks in when explicitly configured on top of the baseline
        # spread_factor above.
        flatness = 0.0
        std_spread = 0.0
        if len(effective) >= 3:
            mean = sum(effective) / len(effective)
            std_spread = (sum((s - mean) ** 2 for s in effective) / len(effective)) ** 0.5
            if self.spread_penalty > 0 and std_spread < self.min_spread:
                flatness = 1.0 - std_spread / self.min_spread
                final *= 1.0 - self.spread_penalty * flatness

        # Optional semantic judge blend (LLM-as-judge).
        semantic: float | None = None
        if self._judge is not None:
            try:
                semantic = max(0.0, min(1.0, float(self._judge(query, [h.get("content", "") for h in top]))))
                final = (1.0 - self.judge_weight) * final + self.judge_weight * semantic
            except Exception:
                semantic = None  # judge failure must never break routing

        final = max(0.0, min(1.0, final))

        if final >= self.use_threshold:
            decision: CragDecision = "use"
        elif final >= self.rewrite_threshold:
            decision = "rewrite"
        else:
            decision = "fallback"

        return CragResult(
            score=final,
            decision=decision,
            relevance=relevance,
            coverage=coverage,
            detail={
                "k": len(top),
                "alpha": self.alpha,
                "spread_factor": round(spread_factor, 4),
                "flatness": round(flatness, 4),
                "semantic": semantic,
            },
        )
