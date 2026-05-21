"""Real CRAG scorer used by the evaluator node.

CRAG (Yan et al., 2024) augments RAG by classifying retrieved evidence
into correct / ambiguous / incorrect and routing the agent accordingly.
We combine two signals:

1. **Relevance** — mean cross-encoder rerank score across the top-K hits
   (when present); falls back to the mean raw score. Cross-encoder scoring
   is dependency-injected.
2. **Coverage** — fraction of the top-K hits whose score exceeds a
   confidence floor; this captures "does the evidence set look coherent".

Final score = ``alpha * relevance + (1 - alpha) * coverage`` and is
mapped to a decision via the thresholds locked in the v3.1 spec.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, Sequence

CragDecision = Literal["use", "rewrite", "fallback"]
Scorer = Callable[[str, Sequence[str]], list[float]]


@dataclass
class CragResult:
    score: float
    decision: CragDecision
    relevance: float
    coverage: float
    detail: dict


class CragScorer:
    """Pluggable CRAG scorer.

    Thresholds default to the v3.1 spec:
      * score >= 0.7        → ``use``
      * 0.3 <= score < 0.7  → ``rewrite``
      * score < 0.3         → ``fallback``
    """

    def __init__(
        self,
        *,
        scorer: Scorer | None = None,
        use_threshold: float = 0.7,
        rewrite_threshold: float = 0.3,
        coverage_floor: float = 0.5,
        alpha: float = 0.7,
        top_k: int = 5,
    ) -> None:
        if not (0.0 <= rewrite_threshold < use_threshold <= 1.0):
            raise ValueError("thresholds must satisfy 0 <= rewrite < use <= 1")
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be in [0, 1]")
        self._scorer = scorer
        self.use_threshold = use_threshold
        self.rewrite_threshold = rewrite_threshold
        self.coverage_floor = coverage_floor
        self.alpha = alpha
        self.top_k = top_k

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
            rerank_scores = [h.get("rerank_score") for h in top if h.get("rerank_score") is not None]
            if rerank_scores:
                relevance = sum(rerank_scores) / len(rerank_scores)
            else:
                raw_scores = [float(h.get("score", 0.0)) for h in top]
                relevance = sum(raw_scores) / len(raw_scores) if raw_scores else 0.0

        # Coverage: fraction of hits whose effective score >= coverage_floor.
        effective = [
            float(h.get("rerank_score") if h.get("rerank_score") is not None else h.get("score", 0.0))
            for h in top
        ]
        coverage = sum(1 for s in effective if s >= self.coverage_floor) / len(effective)

        final = self.alpha * relevance + (1.0 - self.alpha) * coverage
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
            detail={"k": len(top), "alpha": self.alpha},
        )
