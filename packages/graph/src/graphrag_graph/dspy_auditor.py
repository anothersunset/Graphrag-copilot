"""DSPy 2.5 auditor module.

v3.2: Signature now also emits sentence-level ``claims``. The LM is
dependency-injected so tests + offline runs work without an API key. If
DSPy isn't installed, ``DSPyAuditor.audit`` raises and the auditor node
falls back to the heuristic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from .claims import Claim, coerce_claims

logger = logging.getLogger(__name__)


@dataclass
class AuditVerdict:
    verdict: str  # "pass" | "hallucination" | "unsupported"
    rationale: str
    cited_chunk_ids: list[str]
    claims: list[Claim] = field(default_factory=list)


class _LMLike(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


class DSPyAuditor:
    """DSPy-backed auditor.

    In production, ``module`` is a compiled DSPy ChainOfThought; in tests,
    inject any callable matching the same ``__call__`` signature.
    """

    def __init__(self, *, lm: _LMLike | None = None, module: Any | None = None) -> None:
        self._lm = lm
        self._module = module

    def _ensure_module(self):
        if self._module is not None:
            return self._module
        try:
            import dspy  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "DSPyAuditor requires dspy. Install with the [dspy] extra."
            ) from e

        if self._lm is not None:
            dspy.settings.configure(lm=self._lm)

        class _AuditSignature(dspy.Signature):  # type: ignore
            """Audit a generated answer against the cited contexts.

            Emit a verdict, a rationale, the chunk ids that the answer
            cites, and a per-sentence breakdown of which evidence ids
            support each claim.
            """

            question: str = dspy.InputField()
            contexts: list[str] = dspy.InputField()
            draft_answer: str = dspy.InputField()
            verdict: str = dspy.OutputField(desc="pass | hallucination | unsupported")
            rationale: str = dspy.OutputField()
            cited_chunk_ids: list[str] = dspy.OutputField()
            claims: list[dict] = dspy.OutputField(
                desc=(
                    "list of {text, evidence_ids, support} dicts — one per"
                    " sentence of draft_answer, where support is one of"
                    " supported|partial|unsupported"
                )
            )

        self._module = dspy.ChainOfThought(_AuditSignature)
        return self._module

    def audit(
        self,
        *,
        question: str,
        contexts: list[str],
        draft_answer: str,
        chunk_ids: list[str] | None = None,
    ) -> AuditVerdict:
        module = self._ensure_module()
        try:
            result = module(question=question, contexts=contexts, draft_answer=draft_answer)
        except Exception:
            logger.exception("DSPy auditor invocation failed")
            return AuditVerdict(
                verdict="unsupported",
                rationale="auditor invocation failed",
                cited_chunk_ids=[],
                claims=[],
            )

        verdict = str(getattr(result, "verdict", "") or "unsupported").strip().lower()
        rationale = str(getattr(result, "rationale", "") or "")
        cited = getattr(result, "cited_chunk_ids", None) or chunk_ids or []
        if isinstance(cited, str):
            cited = [c.strip() for c in cited.split(",") if c.strip()]
        claims = coerce_claims(getattr(result, "claims", None))
        return AuditVerdict(
            verdict=verdict,
            rationale=rationale,
            cited_chunk_ids=list(cited),
            claims=claims,
        )
