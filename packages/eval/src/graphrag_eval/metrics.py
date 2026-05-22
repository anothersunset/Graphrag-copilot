"""Custom GraphRAG-Copilot evaluation metrics.

Four built-in metrics from v3.1:
  - trace_completeness(audit): every required node fired (planner,
    retriever, evaluator, auditor, generator|fallback).
  - tool_call_necessity(tool_calls, audit): fraction of tool calls
    that contributed to cited evidence.
  - audit_coverage(audit, decisions): fraction of audit entries that
    have corresponding decisions.
  - crag_fix_rate(runs): fraction of pre-rewrite low-coverage runs
    that post-rewrite cleared the use threshold.

v3.2 adds:
  - provenance_sufficiency_score(...): scalar in [0,1]; re-export of
    provenance.provenance_sufficiency for ergonomics.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping, Sequence

from .provenance import ProvenanceReport, provenance_sufficiency

EXPECTED_NODES = ("planner", "retriever", "evaluator", "auditor")


def trace_completeness(audit: Sequence[Mapping]) -> float:
    """Fraction of expected nodes that appear in the audit trail.

    Returns 1.0 when all EXPECTED_NODES are present. Otherwise returns
    the fraction of expected nodes found (partial credit).
    """
    fired = {a.get("node") for a in audit if isinstance(a, Mapping) or hasattr(a, "get")}
    if not EXPECTED_NODES:
        return 1.0
    hit = sum(1 for n in EXPECTED_NODES if n in fired)
    return hit / len(EXPECTED_NODES)


def tool_call_necessity(tool_calls: Sequence, audit: Sequence[Mapping]) -> float:
    """Fraction of tool calls whose output was cited in the audit.

    Returns 1.0 when there are no tool calls (vacuously true).
    """
    if not tool_calls:
        return 1.0
    # Collect all cited tool names from audit entries
    cited: set[str] = set()
    for entry in audit:
        detail = entry.get("detail") or {}
        cited_tools = detail.get("cited_tools") or []
        cited.update(cited_tools)
    tool_names = {t.get("name") if isinstance(t, Mapping) else str(t) for t in tool_calls}
    if not tool_names:
        return 1.0
    return round(len(cited & tool_names) / len(tool_names), 4)


def audit_coverage(
    audit: Sequence[Mapping],
    decisions: Sequence[Mapping] | None = None,
    *,
    required_nodes: Sequence[str] = EXPECTED_NODES,
) -> float:
    """Fraction of audit entries that have corresponding decisions.

    If ``decisions`` is None, returns 1.0 when ``audit`` is empty.
    """
    if not decisions:
        return 1.0
    audit_nodes = {a.get("node") for a in audit if isinstance(a, Mapping)}
    decision_nodes = {d.get("node") for d in decisions if isinstance(d, Mapping)}
    if not decision_nodes:
        return 1.0
    hit = sum(1 for n in decision_nodes if n in audit_nodes)
    return round(hit / len(decision_nodes), 4)


def crag_fix_rate(runs: Iterable[Mapping]) -> float:
    """Fraction of rewrite runs that recovered to 'use' decision.

    Only counts runs with ``rewrite_iterations > 0``.
    """
    pre_low = 0
    fixed = 0
    for r in runs:
        rewrite_iters = r.get("rewrite_iterations", 0)
        if rewrite_iters > 0:
            pre_low += 1
            if (r.get("final_decision") or "").lower() == "use":
                fixed += 1
    if pre_low == 0:
        return 0.0
    return fixed / pre_low


def provenance_sufficiency_score(
    *,
    answer: str,
    claims: Iterable[dict],
    cited_chunk_ids: Iterable[str],
    chunk_contents: dict[str, str],
    **kwargs,
) -> float:
    """Ergonomic wrapper — returns just the scalar score."""
    report: ProvenanceReport = provenance_sufficiency(
        answer=answer,
        claims=claims,
        cited_chunk_ids=cited_chunk_ids,
        chunk_contents=chunk_contents,
        **kwargs,
    )
    return report.score


__all__ = [
    "EXPECTED_NODES",
    "trace_completeness",
    "tool_call_necessity",
    "audit_coverage",
    "crag_fix_rate",
    "provenance_sufficiency_score",
]
