"""RAGAS 0.2+ runner with dependency-injected LLM/embeddings."""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, Protocol, cast

logger = logging.getLogger(__name__)


class EvaluateFn(Protocol):
    def __call__(
        self,
        dataset: list[dict[str, object]],
        *,
        metrics: Sequence[str],
        llm: Any | None,
        embeddings: Any | None,
    ) -> Any: ...


@dataclass
class EvalSample:
    question: str
    answer: str
    contexts: list[str]
    ground_truth: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class RagasRunner:
    """Thin RAGAS adapter.

    Tests pass a fake ``ragas_evaluate`` callable so they don't need a live
    LLM. In production, leave it None and the runner uses the official
    ``ragas.evaluate`` entrypoint.
    """

    def __init__(
        self,
        *,
        llm: Any | None = None,
        embeddings: Any | None = None,
        metric_names: Sequence[str] = (
            "context_precision",
            "context_recall",
            "faithfulness",
        ),
        evaluate_fn: EvaluateFn | None = None,
    ) -> None:
        self.llm = llm
        self.embeddings = embeddings
        self.metric_names = list(metric_names)
        self._evaluate_fn = evaluate_fn

    def _load_evaluate(self) -> EvaluateFn:
        if self._evaluate_fn is not None:
            return self._evaluate_fn
        try:
            module = import_module("ragas")
            evaluate = module.evaluate
        except (ImportError, AttributeError) as e:
            raise RuntimeError(
                "RagasRunner requires ragas. Install with 'graphrag-eval[ragas]'."
            ) from e
        return cast(EvaluateFn, evaluate)

    def run(self, samples: Sequence[EvalSample]) -> dict[str, float]:
        if not samples:
            return {m: 0.0 for m in self.metric_names}
        evaluate = self._load_evaluate()
        dataset = [
            {
                "question": s.question,
                "answer": s.answer,
                "contexts": list(s.contexts),
                "ground_truth": s.ground_truth or "",
            }
            for s in samples
        ]
        try:
            result = evaluate(
                dataset,
                metrics=self.metric_names,
                llm=self.llm,
                embeddings=self.embeddings,
            )
        except Exception:
            logger.exception("ragas evaluate failed")
            return {m: float("nan") for m in self.metric_names}
        # Result objects expose .scores or be dict-like; coerce to floats.
        if hasattr(result, "to_pandas"):
            df = result.to_pandas()
            return {m: float(df[m].mean()) for m in self.metric_names if m in df.columns}
        if isinstance(result, dict):
            return {m: float(result.get(m, float("nan"))) for m in self.metric_names}
        return {m: float("nan") for m in self.metric_names}
