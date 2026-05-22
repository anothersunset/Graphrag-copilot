"""Run both bench suites and aggregate v3.2 KPIs."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Sequence

from graphrag_eval.adversarial import (
    AdversarialReport,
    DistractorCase,
    Orchestrator as AdversarialOrchestrator,
    run_adversarial,
)
from graphrag_eval.provenance import ProvenanceReport, provenance_sufficiency

from .corpus import CORPUS
from .questions import BENCH_DISTRACTORS, GOLD_QUESTIONS, BenchQuestion
from .reference_runner import (
    BenchOrchestrator,
    adversarial_orchestrator_adapter,
    reference_orchestrator,
)


@dataclass
class QuestionResult:
    question_id: str
    question: str
    language: str
    category: str
    provenance: ProvenanceReport
    cited_chunk_ids: list[str]
    answer: str
    expected_chunk_ids: list[str] = field(default_factory=list)


@dataclass
class ProvenanceBenchReport:
    """Aggregated KPIs across the gold suite and the adversarial suite."""

    questions_evaluated: int
    ps_mean: float
    ps_median: float
    ps_pass_rate: float
    ps_floor: float
    question_results: list[QuestionResult]
    adversarial: AdversarialReport

    # v3.2 KPI floors / ceilings.
    ps_target: float = 0.80
    misled_max: float = 0.10
    hallucination_max: float = 0.10
    distractor_visited_min: float = 0.50

    def all_kpis_pass(self) -> bool:
        return (
            self.ps_mean >= self.ps_target
            and self.adversarial.misled_rate <= self.misled_max
            and self.adversarial.hallucination_rate <= self.hallucination_max
            and self.adversarial.distractor_visited_rate >= self.distractor_visited_min
        )


def run_bench(
    *,
    orchestrator: BenchOrchestrator | None = None,
    adversarial_orchestrator: AdversarialOrchestrator | None = None,
    questions: Sequence[BenchQuestion] | None = None,
    distractors: Sequence[DistractorCase] | None = None,
    ps_floor: float = 0.80,
) -> ProvenanceBenchReport:
    """Run both suites and return aggregated KPIs.

    ``orchestrator(question) -> dict`` answers gold questions.
    ``adversarial_orchestrator(question, list[dict]) -> dict`` answers
    adversarial cases with a planted distractor in the corpus. Both
    default to the bench's deterministic reference implementations.
    """
    orch = orchestrator or reference_orchestrator
    adv_orch = adversarial_orchestrator or adversarial_orchestrator_adapter
    qs = tuple(questions) if questions is not None else GOLD_QUESTIONS
    ds = tuple(distractors) if distractors is not None else BENCH_DISTRACTORS

    chunk_contents = {c.id: c.text for c in CORPUS}

    results: list[QuestionResult] = []
    for q in qs:
        out = orch(q.question)
        ps = provenance_sufficiency(
            answer=str(out.get("answer") or ""),
            claims=out.get("claims") or [],
            cited_chunk_ids=out.get("cited_chunk_ids") or [],
            chunk_contents=chunk_contents,
        )
        results.append(
            QuestionResult(
                question_id=q.id,
                question=q.question,
                language=q.language,
                category=q.category,
                provenance=ps,
                cited_chunk_ids=list(out.get("cited_chunk_ids") or []),
                answer=str(out.get("answer") or ""),
                expected_chunk_ids=list(q.gold_chunk_ids),
            )
        )

    ps_scores = [r.provenance.score for r in results] or [0.0]
    ps_mean = round(statistics.fmean(ps_scores), 4)
    ps_median = round(statistics.median(ps_scores), 4)
    ps_pass_rate = round(
        sum(1 for s in ps_scores if s >= ps_floor) / len(ps_scores), 4
    )

    adv_report = run_adversarial(ds, adv_orch)

    return ProvenanceBenchReport(
        questions_evaluated=len(results),
        ps_mean=ps_mean,
        ps_median=ps_median,
        ps_pass_rate=ps_pass_rate,
        ps_floor=ps_floor,
        question_results=results,
        adversarial=adv_report,
    )
