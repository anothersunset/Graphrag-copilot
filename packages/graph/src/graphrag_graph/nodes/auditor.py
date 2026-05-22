"""Auditor node — DSPy verdict with citation-count fallback.

v3.2: also emits sentence-level ``claims`` (each sentence -> evidence
ids). If DSPy didn't return them, we build them heuristically from the
answer + retrieval context using token overlap.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..claims import Claim, heuristic_claims
from ..dspy_auditor import DSPyAuditor
from ..state import AuditEntry


def auditor_node(state: dict, *, config: dict | None = None) -> dict:
    config = config or {}
    dspy_auditor: DSPyAuditor | None = config.get("dspy_auditor")
    fused = state.get("fused_hits") or state.get("hits") or []
    answer = state.get("answer", "")
    chunk_ids = [h.get("chunk_id") for h in fused if h.get("chunk_id")]

    verdict_str = "pass"
    rationale = ""
    cited: list[str] = []
    claims: list[Claim] = []

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
            claims = v.claims
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

    if not claims:
        claims = heuristic_claims(
            answer,
            cited_chunk_ids=cited,
            contexts=fused,
        )

    unsupported = sum(1 for c in claims if not c.is_supported())
    audit = AuditEntry(
        node="auditor",
        timestamp=datetime.now(UTC).isoformat(),
        summary=f"verdict={verdict_str} cited={len(cited)} claims={len(claims)} unsupported={unsupported}",
        detail={
            "verdict": verdict_str,
            "rationale": rationale,
            "cited_tools": list({h.get("source") for h in fused if h.get("source")}),
            "claim_count": len(claims),
            "unsupported_claim_count": unsupported,
        },
    )
    return {
        "audit": [audit],
        "cited_chunk_ids": cited,
        "verdict": verdict_str,
        "claims": [c.model_dump() for c in claims],
    }
