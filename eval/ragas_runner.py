"""RAGAS / DeepEval 自动指标接入模块.

职责: 接入 RAGAS / DeepEval 自动指标 (faithfulness/context_precision/context_recall 等)。
依赖注入: 测试时可传入 fake evaluate_fn，生产环境使用 ragas.evaluate。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from eval.graphrag_client import GoldCase, QueryResult

logger = logging.getLogger(__name__)


@dataclass
class EvalSample:
    """RAGAS 评测样本."""
    question: str
    answer: str
    contexts: List[str]
    ground_truth: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class RagasRunner:
    """RAGAS 0.2+ runner with dependency-injected LLM/embeddings.

    测试时传入 fake evaluate_fn 避免依赖真实 LLM。
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
        evaluate_fn: Any | None = None,
    ) -> None:
        self.llm = llm
        self.embeddings = embeddings
        self.metric_names = list(metric_names)
        self._evaluate_fn = evaluate_fn

    def _load_evaluate(self):
        if self._evaluate_fn is not None:
            return self._evaluate_fn
        try:
            from ragas import evaluate as _ragas_evaluate
        except ImportError as e:
            raise RuntimeError(
                "RagasRunner requires ragas. Install with 'pip install ragas'."
            ) from e
        return _ragas_evaluate

    def run(self, samples: Sequence[EvalSample]) -> Dict[str, float]:
        """运行 RAGAS 评测.

        Args:
            samples: 评测样本列表

        Returns:
            指标名 -> 平均值的字典
        """
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


def build_eval_samples(cases: List[GoldCase], results: List[QueryResult]) -> List[EvalSample]:
    """从 GoldCase 和 QueryResult 构建 RAGAS 评测样本.

    Args:
        cases: gold 用例列表
        results: 查询结果列表

    Returns:
        EvalSample 列表
    """
    samples = []
    for case, result in zip(cases, results):
        samples.append(EvalSample(
            question=case.question,
            answer=result.answer,
            contexts=result.contexts,
            ground_truth=case.gold_answer,
            metadata={"case_id": case.id, "type": case.type},
        ))
    return samples


def run_ragas(cases: List[GoldCase], results: List[QueryResult]) -> Dict[str, float]:
    """便捷入口: 构建样本并运行 RAGAS.

    Args:
        cases: gold 用例列表
        results: 查询结果列表

    Returns:
        指标名 -> 平均值的字典
    """
    samples = build_eval_samples(cases, results)
    runner = RagasRunner()
    return runner.run(samples)
