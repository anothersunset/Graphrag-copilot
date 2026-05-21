"""Provenance Sufficiency — can a reader reproduce the answer from the
cited evidence alone?

We approximate this without an LLM by combining two checks:

1. **Sentence-level recall.** For every supported claim, at least one of
   its evidence_ids must appear in ``cited_chunk_ids`` *and* the cited
   chunk's content must share ≥ ``min_overlap`` significant tokens with
   the claim text. Unsupported claims count against recall.
2. **Answer-level coverage.** The cited chunks combined must cover at
   least ``coverage_floor`` of the answer's significant tokens.

The entailer is dependency-injected so offline runs can swap in a
BGE-Reranker-v2-m3 cross-encoder or a small NLI model for higher
fidelity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol


class _Entailer(Protocol):
    def __call__(self, *, premise: str, hypothesis: str) -> float:
        """Return entailment score in [0, 1] — 1 = fully entailed."""
        ...


@dataclass
class ClaimVerdict:
    text: str
    evidence_ids: list[str]
    supported_by: list[str] = field(default_factory=list)
    sufficient: bool = False
    entailment: float | None = None


@dataclass
class ProvenanceReport:
    score: float
    sentence_recall: float
    coverage: float
    claim_verdicts: list[ClaimVerdict] = field(default_factory=list)
    missing_evidence_claims: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "sentence_recall": self.sentence_recall,
            "coverage": self.coverage,
            "missing_evidence_claims": list(self.missing_evidence_claims),
            "claim_verdicts": [
                {
                    "text": v.text,
                    "evidence_ids": v.evidence_ids,
                    "supported_by": v.supported_by,
                    "sufficient": v.sufficient,
                    "entailment": v.entailment,
                }
                for v in self.claim_verdicts
            ],
        }


_TOKEN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z][A-Za-z0-9_]+")


def _tokens(s: str) -> set[str]:
    if not s:
        return set()
    return {t.lower() for t in _TOKEN.findall(s) if len(t) >= 2 or (len(t) == 1 and "\u4e00" <= t <= "\u9fff")}


def provenance_sufficiency(
    *,
    answer: str,
    claims: Iterable[dict],
    cited_chunk_ids: Iterable[str],
    chunk_contents: dict[str, str],
    coverage_floor: float = 0.5,
    min_overlap: int = 2,
    entailer: _Entailer | None = None,
    entailment_floor: float = 0.4,
    recall_weight: float = 0.7,
) -> ProvenanceReport:
    cited_set = set(cited_chunk_ids)
    answer_tokens = _tokens(answer)

    # 1. Sentence-level recall.
    verdicts: list[ClaimVerdict] = []
    missing: list[str] = []
    sufficient_count = 0
    total_claims = 0

    for claim in claims:
        text = claim.get("text", "") if isinstance(claim, dict) else getattr(claim, "text", "")
        evidence_ids = list(
            claim.get("evidence_ids", []) if isinstance(claim, dict) else getattr(claim, "evidence_ids", [])
        )
        if not text.strip():
            continue
        total_claims += 1
        claim_tokens = _tokens(text)
        supported_by: list[str] = []
        ent_score: float | None = None
        for eid in evidence_ids:
            if eid not in cited_set:
                continue
            content = chunk_contents.get(eid, "")
            if not content:
                continue
            overlap = len(claim_tokens & _tokens(content))
            ok = overlap >= min_overlap
            if not ok and entailer is not None:
                score = float(entailer(premise=content, hypothesis=text))
                ent_score = max(ent_score or 0.0, score)
                ok = score >= entailment_floor
            if ok:
                supported_by.append(eid)

        sufficient = bool(supported_by)
        if sufficient:
            sufficient_count += 1
        else:
            missing.append(text)
        verdicts.append(
            ClaimVerdict(
                text=text,
                evidence_ids=evidence_ids,
                supported_by=supported_by,
                sufficient=sufficient,
                entailment=ent_score,
            )
        )

    sentence_recall = sufficient_count / total_claims if total_claims else 0.0

    # 2. Answer-level coverage.
    covered: set[str] = set()
    for eid in cited_set:
        covered |= _tokens(chunk_contents.get(eid, ""))
    coverage = (
        len(answer_tokens & covered) / len(answer_tokens) if answer_tokens else 0.0
    )
    coverage_bonus = 1.0 if coverage >= coverage_floor else coverage / coverage_floor

    score = recall_weight * sentence_recall + (1.0 - recall_weight) * coverage_bonus

    return ProvenanceReport(
        score=round(score, 4),
        sentence_recall=round(sentence_recall, 4),
        coverage=round(coverage, 4),
        claim_verdicts=verdicts,
        missing_evidence_claims=missing,
    )


def make_bge_entailer(reranker: Callable[..., float]) -> _Entailer:
    """Adapt a BGE-Reranker score function to the entailer protocol."""

    def _ent(*, premise: str, hypothesis: str) -> float:
        raw = float(reranker(query=hypothesis, passage=premise))
        # cross-encoders typically emit logits; squash to [0, 1].
        return 1.0 / (1.0 + pow(2.71828, -raw))

    return _ent
