"""Auditor node — post-generation faithfulness + citation verification."""
from __future__ import annotations

import logging
from typing import Any

from .._utils import digest, now_iso
from ..state import GraphState

logger = logging.getLogger(__name__)


def auditor_node(
    state: GraphState, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    cfg = config or {}
    auditor = cfg.get("auditor_client")
    strict = bool(cfg.get("auditor_strict", False))

    question = state["question"]
    answer = state.get("answer", "")
    citations = state.get("citations", [])

    if auditor is not None:
        report = auditor.audit(
            question=question, answer=answer, citations=citations
        )
        verdict = report.get("verdict", "pass")
        notes = list(report.get("notes", []))
    else:
        # Heuristic fallback used in tests / dry runs:
        #   - non-empty answer + at least 1 citation → pass
        #   - else → warn
        if answer and citations:
            verdict, notes = "pass", []
        else:
            verdict, notes = "warn", ["no citations or empty answer"]

    if strict and verdict == "warn":
        verdict = "fail"

    audit = {
        "node": "auditor",
        "decision": verdict,
        "rationale": "; ".join(notes) if notes else "ok",
        "inputs_digest": digest(
            {"q": question, "a": answer[:200], "n_cites": len(citations)}
        ),
        "outputs_digest": digest({"verdict": verdict, "notes": notes}),
        "timestamp": now_iso(),
    }

    return {
        "auditor_verdict": verdict,
        "auditor_notes": notes,
        "audit": [audit],
    }
