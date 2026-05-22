"""DeepEval 2.x adapter with dependency-injected judge."""
from __future__ import annotations

import logging
from typing import Any, Sequence

from .ragas_runner import EvalSample

logger = logging.getLogger(__name__)


class DeepEvalRunner:
    """Run DeepEval metrics (hallucination, answer_relevancy, bias)."""

    def __init__(
        self,
        *,
        judge: Any | None = None,
        metric_names: Sequence[str] = (
            "hallucination",
            "answer_relevancy",
            "bias",
        ),
        evaluate_fn: Any | None = None,
    ) -> None:
        self.judge = judge
        self.metric_names = list(metric_names)
        self._evaluate_fn = evaluate_fn

    def _load_evaluate(self):
        if self._evaluate_fn is not None:
            return self._evaluate_fn
        try:
            from deepeval import evaluate as _deepeval_evaluate  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "DeepEvalRunner requires deepeval. Install with 'graphrag-eval[deepeval]'."
            ) from e
        return _deepeval_evaluate

    def run(self, samples: Sequence[EvalSample]) -> dict[str, float]:
        if not samples:
            return {m: 0.0 for m in self.metric_names}
        evaluate = self._load_evaluate()
        cases = [
            {
                "input": s.question,
                "actual_output": s.answer,
                "retrieval_context": list(s.contexts),
                "expected_output": s.ground_truth or "",
            }
            for s in samples
        ]
        try:
            result = evaluate(
                cases,
                metrics=self.metric_names,
                judge=self.judge,
            )
        except Exception:
            logger.exception("deepeval evaluate failed")
            return {m: float("nan") for m in self.metric_names}
        if isinstance(result, dict):
            return {m: float(result.get(m, float("nan"))) for m in self.metric_names}
        return {m: float("nan") for m in self.metric_names}
