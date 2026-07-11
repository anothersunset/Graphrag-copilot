"""Evaluation harness for GraphRAG Copilot v3.1."""

from .deepeval_runner import DeepEvalRunner
from .metrics import (
    EXPECTED_NODES,
    answer_point_recall,
    audit_coverage,
    citation_precision,
    citation_recall,
    citation_validity,
    crag_fix_rate,
    retrieval_recall_at_k,
    tool_call_necessity,
    trace_completeness,
)
from .ragas_runner import EvalSample, RagasRunner

__version__ = "0.1.0"

__all__ = [
    "EXPECTED_NODES",
    "DeepEvalRunner",
    "EvalSample",
    "RagasRunner",
    "__version__",
    "answer_point_recall",
    "audit_coverage",
    "citation_precision",
    "citation_recall",
    "citation_validity",
    "crag_fix_rate",
    "retrieval_recall_at_k",
    "tool_call_necessity",
    "trace_completeness",
]
