"""Evaluation harness for GraphRAG Copilot v3.1."""
from .deepeval_runner import DeepEvalRunner
from .metrics import (
    EXPECTED_NODES,
    audit_coverage,
    crag_fix_rate,
    tool_call_necessity,
    trace_completeness,
)
from .ragas_runner import EvalSample, RagasRunner

__version__ = "0.1.0"

__all__ = [
    "DeepEvalRunner",
    "EXPECTED_NODES",
    "EvalSample",
    "RagasRunner",
    "__version__",
    "audit_coverage",
    "crag_fix_rate",
    "tool_call_necessity",
    "trace_completeness",
]
