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

from collections.abc import Iterable, Mapping, Sequence

from .provenance import ProvenanceReport, provenance_sufficiency

EXPECTED_NODES = ("planner", "retriever", "evaluator", "generator", "auditor")
_FALLBACK_NODES = ("planner", "retriever", "evaluator", "fallback", "auditor")


def trace_completeness(audit: Sequence[Mapping]) -> float:
    """Fraction of expected nodes that appear in the audit trail.

    Returns 1.0 when all EXPECTED_NODES are present. Otherwise returns
    the fraction of expected nodes found (partial credit).
    """
    fired = {
        entry.get("node") or entry.get("node_name") for entry in audit if isinstance(entry, Mapping)
    }
    expected = _FALLBACK_NODES if "fallback" in fired else EXPECTED_NODES
    if not expected:
        return 1.0
    hit = sum(1 for node in expected if node in fired)
    return hit / len(expected)


def tool_call_necessity(tool_calls: Sequence, audit: Sequence[Mapping]) -> float:
    """Fraction of tool calls whose output was cited in the audit.

    Returns 1.0 when there are no tool calls (vacuously true).
    """
    if not tool_calls:
        return 1.0
    # Collect all cited tool names from audit entries
    cited: set[str] = set()
    for entry in audit:
        detail = entry.get("detail") or entry.get("payload") or {}
        if not isinstance(detail, Mapping):
            continue
        cited_tools = detail.get("cited_tools") or []
        cited.update(str(tool) for tool in cited_tools)
    tool_names = {
        str(tool.get("name") or tool.get("tool")) if isinstance(tool, Mapping) else str(tool)
        for tool in tool_calls
    }
    tool_names.discard("None")
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
    audit_nodes = {
        entry.get("node") or entry.get("node_name") for entry in audit if isinstance(entry, Mapping)
    }
    decision_nodes = {
        decision.get("node") or decision.get("node_name")
        for decision in (decisions or [])
        if isinstance(decision, Mapping)
    }
    expected_nodes = decision_nodes or set(required_nodes)
    if not expected_nodes:
        return 1.0
    hit = sum(1 for node in expected_nodes if node in audit_nodes)
    return round(hit / len(expected_nodes), 4)


def crag_fix_rate(runs: Iterable[Mapping]) -> float:
    """Fraction of rewrite runs that recovered to 'use' decision.

    Only counts runs with ``rewrite_iterations > 0``.
    """
    pre_low = 0
    fixed = 0
    for r in runs:
        rewrite_iters = r.get("rewrite_iterations", r.get("rewrite_iteration", 0))
        if rewrite_iters > 0:
            pre_low += 1
            final_decision = r.get("final_decision") or r.get("crag_decision") or ""
            if str(final_decision).lower() == "use":
                fixed += 1
    if pre_low == 0:
        return 0.0
    return fixed / pre_low


def retrieval_recall_at_k(
    retrieved_chunk_ids: Sequence[str],
    required_evidence_ids: Sequence[str],
    *,
    k: int = 5,
) -> float:
    """Fraction of required evidence present in the first ``k`` retrievals."""
    required = set(required_evidence_ids)
    if not required:
        return 1.0
    retrieved = set(retrieved_chunk_ids[:k])
    return round(len(retrieved & required) / len(required), 4)


def answer_point_recall(
    answer: str,
    required_points: Sequence[str],
    *,
    forbidden_points: Sequence[str] = (),
) -> float:
    """Deterministic expected-answer coverage with an explicit forbidden gate."""
    normalized = " ".join(answer.casefold().replace("％", "%").split())
    forbidden = [
        point
        for point in forbidden_points
        if " ".join(point.casefold().replace("％", "%").split()) in normalized
    ]
    if forbidden:
        return 0.0
    required = {
        " ".join(point.casefold().replace("％", "%").split())
        for point in required_points
        if point.strip()
    }
    if not required:
        return 1.0
    return round(sum(point in normalized for point in required) / len(required), 4)


def citation_precision(
    cited_chunk_ids: Sequence[str], required_evidence_ids: Sequence[str]
) -> float:
    """Fraction of cited chunks that are gold evidence for the case."""
    cited = set(cited_chunk_ids)
    required = set(required_evidence_ids)
    if not cited:
        return 1.0 if not required else 0.0
    return round(len(cited & required) / len(cited), 4)


def citation_recall(cited_chunk_ids: Sequence[str], required_evidence_ids: Sequence[str]) -> float:
    """Fraction of gold evidence chunks cited by the answer."""
    required = set(required_evidence_ids)
    if not required:
        return 1.0 if not cited_chunk_ids else 0.0
    cited = set(cited_chunk_ids)
    return round(len(cited & required) / len(required), 4)


def citation_validity(
    *,
    cited_chunk_ids: Sequence[str],
    retrieved_chunk_ids: Sequence[str],
    claims: Sequence[Mapping],
) -> float:
    """Return 1 when every citation and claim edge resolves to retrieved evidence."""
    cited = set(cited_chunk_ids)
    retrieved = set(retrieved_chunk_ids)
    if not cited.issubset(retrieved):
        return 0.0
    for claim in claims:
        evidence_ids = {str(value) for value in claim.get("evidence_ids") or []}
        if not evidence_ids.issubset(cited) or not evidence_ids.issubset(retrieved):
            return 0.0
    return 1.0


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
    "answer_point_recall",
    "audit_coverage",
    "citation_precision",
    "citation_recall",
    "citation_validity",
    "crag_fix_rate",
    "provenance_sufficiency_score",
    "retrieval_recall_at_k",
    "tool_call_necessity",
    "trace_completeness",
]
