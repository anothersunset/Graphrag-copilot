"""Custom GraphRAG-Copilot evaluation metrics.

Four built-in metrics from v3.1:
  - trace_completeness(run): every required node fired (planner,
    retriever, evaluator, auditor, generator|fallback).
  - tool_call_necessity(run): ∥tool calls∥ / ∥unique evidence∥ ∈ [0.9, 1.1].
  - audit_coverage(audit_entries): one audit per node.
  - crag_fix_rate(runs): fraction of pre-rewrite low-coverage runs that
    post-rewrite cleared the use threshold.

v3.2 adds:
  - provenance_sufficiency_score(...): scalar in [0,1]; re-export of
    provenance.provenance_sufficiency for ergonomics.
"""
from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping, Sequence

from .provenance import ProvenanceReport, provenance_sufficiency

_REQUIRED_NODES = ("planner", "retriever", "evaluator", "auditor")


def trace_completeness(run: Mapping) -> float:
    audit = run.get("audit") or []
    fired = {a.get("node") for a in audit if isinstance(a, Mapping) or hasattr(a, "get")}
    if not all(node in fired for node in _REQUIRED_NODES):
        return 0.0
    if not ({"generator", "fallback"} & fired):
        return 0.0
    return 1.0


def tool_call_necessity(run: Mapping) -> float:
    tool_calls = run.get("tool_calls") or []
    evidence = run.get("cited_chunk_ids") or run.get("fused_hits") or []
    unique_evidence = {
        e if isinstance(e, str) else (e.get("chunk_id") if hasattr(e, "get") else str(e))
        for e in evidence
    }
    if not unique_evidence:
        return 0.0
    return round(len(tool_calls) / len(unique_evidence), 4)


def audit_coverage(audit_entries: Sequence, *, required_nodes: Sequence[str] = _REQUIRED_NODES) -> float:
    fired = Counter()
    for entry in audit_entries:
        node = entry.get("node") if isinstance(entry, Mapping) else getattr(entry, "node", None)
        if node:
            fired[node] += 1
    if not required_nodes:
        return 1.0
    hit = sum(1 for n in required_nodes if fired[n] >= 1)
    return round(hit / len(required_nodes), 4)


def crag_fix_rate(runs: Iterable[Mapping]) -> float:
    pre_low = 0
    fixed = 0
    for r in runs:
        if (r.get("pre_rewrite_decision") or "").lower() == "rewrite":
            pre_low += 1
            if (r.get("post_rewrite_decision") or "").lower() == "use":
                fixed += 1
    if pre_low == 0:
        return 0.0
    return round(fixed / pre_low, 4)


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
    "trace_completeness",
    "tool_call_necessity",
    "audit_coverage",
    "crag_fix_rate",
    "provenance_sufficiency_score",
]
