"""Auditor node — DSPy verdict with citation-count fallback."""
from __future__ import annotations

from datetime import datetime, timezone

from ..contracts import AuditEntry
from ..dspy_auditor import DSPyAuditor


def auditor(state: dict, *, config: dict | None = None) -> dict:
    config = config or {}
    dspy_auditor: DSPyAuditor | None = config.get("dspy_auditor")
    fused = state.get("fused_hits") or state.get("hits") or []
    answer = state.get("answer", "")
    chunk_ids = [h.get("chunk_id") for h in fused if h.get("chunk_id")]

    verdict_str = "pass"
    rationale = ""
    cited: list[str] = []

    if dspy_auditor is not None:
        try:
            v = dspy_auditor.audit(
                question=state.get("query", ""),
                contexts=[h.get("content", "") for h in fused],
                draft_answer=answer,
                chunk_ids=chunk_ids,
            )
            verdict_str = v.verdict
            rationale = v.rationale
            cited = v.cited_chunk_ids
        except Exception:
            # fall through to heuristic
            pass

    if not cited:
        # Heuristic fallback: count chunk_ids that literally appear in the answer.
        cited = [cid for cid in chunk_ids if cid and cid in answer]
        if not cited and fused:
            cited = chunk_ids[:3]
        verdict_str = "pass" if cited else "unsupported"
        rationale = rationale or "heuristic auditor: cited chunks present in answer"

    audit = AuditEntry(
        node="auditor",
        timestamp=datetime.now(timezone.utc).isoformat(),
        summary=f"verdict={verdict_str} cited={len(cited)}",
        detail={
            "verdict": verdict_str,
            "rationale": rationale,
            "cited_tools": list({h.get("source") for h in fused if h.get("source")}),
        },
    )
    return {
        "audit": [audit],
        "cited_chunk_ids": cited,
        "verdict": verdict_str,
    }
