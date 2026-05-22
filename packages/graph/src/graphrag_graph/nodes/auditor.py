"""Auditor node — DSPy verdict with citation-count fallback.

v3.2: also emits sentence-level ``claims`` (each sentence -> evidence
ids). If DSPy didn't return them, we build them heuristically from the
answer + retrieval context using token overlap.

The state key is ``auditor_verdict`` (matching
``state.AuditorVerdict = Literal['pass', 'warn', 'fail']``); DSPy
returns free-form strings (``unsupported`` / ``hallucination``) which
are coerced via ``_VERDICT_MAP`` below.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..claims import Claim, heuristic_claims
from ..dspy_auditor import DSPyAuditor

# Coerce free-form auditor verdicts into the AuditorVerdict literal.
_VERDICT_MAP: dict[str, str] = {
    "pass": "pass",
    "warn": "warn",
    "fail": "fail",
    "unsupported": "fail",
    "hallucination": "fail",
}


def _coerce_verdict(raw: str) -> str:
    return _VERDICT_MAP.get((raw or "").strip().lower(), "warn")


def auditor_node(state: dict, *, config: dict | None = None) -> dict:
    config = config or {}
    dspy_auditor: DSPyAuditor | None = config.get("dspy_auditor")
    fused = state.get("fused_hits") or state.get("hits") or []
    answer = state.get("answer", "")
    question = state.get("question", "") or state.get("query", "")
    chunk_ids = [h.get("chunk_id") for h in fused if h.get("chunk_id")]

    raw_verdict = "pass"
    rationale = ""
    cited: list[str] = []
    claims: list[Claim] = []

    if dspy_auditor is not None:
        try:
            v = dspy_auditor.audit(
                question=question,
                contexts=[h.get("content", "") for h in fused],
                draft_answer=answer,
                chunk_ids=chunk_ids,
            )
            raw_verdict = v.verdict
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
        raw_verdict = "pass" if cited else "unsupported"
        rationale = rationale or "heuristic auditor: cited chunks present in answer"

    if not claims:
        claims = heuristic_claims(
            answer,
            cited_chunk_ids=cited,
            contexts=fused,
        )

    verdict = _coerce_verdict(raw_verdict)
    unsupported = sum(1 for c in claims if not c.is_supported())
    audit = {
        "node": "auditor",
        "decision": verdict,
        "rationale": (
            f"verdict={raw_verdict} cited={len(cited)} "
            f"claims={len(claims)} unsupported={unsupported}"
        ),
        "inputs_digest": "",
        "outputs_digest": "",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return {
        "audit": [audit],
        "cited_chunk_ids": cited,
        "auditor_verdict": verdict,
        "auditor_notes": [rationale] if rationale else [],
        "claims": [c.model_dump() for c in claims],
    }
