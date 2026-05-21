"""Four pure-Python custom Agentic-RAG metrics.

All inputs are plain dicts so this module has zero hard dependency on
graphrag_graph or graphrag_observability. The graph package emits these
shapes; the observability package exports them; this package scores them.
"""
from __future__ import annotations

from typing import Iterable, Sequence

EXPECTED_NODES = (
    "planner",
    "retriever",
    "evaluator",
    "generator",  # OR "fallback" in the bad branch — see trace_completeness
    "auditor",
)


def trace_completeness(audit: Sequence[dict], *, expected: Iterable[str] = EXPECTED_NODES) -> float:
    """Fraction of expected node spans that actually appear in the audit log.

    The auditor is treated as required for a complete run; if the run took
    the fallback branch, generator may be substituted by fallback.
    """
    seen = {entry.get("node") for entry in audit}
    required = set(expected)
    # generator / fallback are interchangeable for completeness
    if "generator" in required and "fallback" in seen and "generator" not in seen:
        required = (required - {"generator"}) | {"fallback"}
    if not required:
        return 1.0
    return len(required & seen) / len(required)


def tool_call_necessity(tool_calls: Sequence[dict], audit: Sequence[dict]) -> float:
    """Ratio of cited tool calls to emitted tool calls.

    A tool call is "cited" if its tool name appears in any audit entry's
    ``detail.cited_tools`` list. Target band [0.9, 1.1] catches both
    over-calling (low ratio) and pre-cited but unused tools (>1).
    """
    if not tool_calls:
        return 1.0
    cited: set[str] = set()
    for entry in audit:
        for name in (entry.get("detail") or {}).get("cited_tools", []):
            cited.add(name)
    emitted = {tc.get("name") for tc in tool_calls if tc.get("name")}
    if not emitted:
        return 1.0
    return len(cited & emitted) / len(emitted)


def audit_coverage(audit: Sequence[dict], decisions: Sequence[dict]) -> float:
    """Fraction of agent decisions that have a matching AuditEntry.

    Each decision in ``decisions`` should expose ``node`` (str). The
    metric returns 1.0 when every decision has at least one corresponding
    audit entry with the same node name.
    """
    if not decisions:
        return 1.0
    nodes_with_audit = {e.get("node") for e in audit}
    covered = sum(1 for d in decisions if d.get("node") in nodes_with_audit)
    return covered / len(decisions)


def crag_fix_rate(runs: Sequence[dict]) -> float:
    """Fraction of runs that entered rewrite at least once and ended in 'use'.

    A run dict shape:
      {
        "rewrite_iterations": int,        # number of rewrite loops
        "final_decision": "use" | "fallback",
      }

    Denominator: runs with rewrite_iterations >= 1.
    Numerator: subset of those that ended with final_decision == 'use'.
    Returns 0.0 if no runs needed rewriting.
    """
    needed_fix = [r for r in runs if int(r.get("rewrite_iterations", 0)) >= 1]
    if not needed_fix:
        return 0.0
    fixed = sum(1 for r in needed_fix if r.get("final_decision") == "use")
    return fixed / len(needed_fix)
