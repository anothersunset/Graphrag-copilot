"""Run both bench suites and aggregate v3.2 KPIs."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field

from graphrag_eval.adversarial import (
    AdversarialReport,
    DistractorCase,
    run_adversarial,
)
from graphrag_eval.adversarial import (
    Orchestrator as AdversarialOrchestrator,
)
from graphrag_eval.metrics import (
    answer_point_recall,
    citation_precision,
    citation_recall,
    citation_validity,
    retrieval_recall_at_k,
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
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    answer_point_recall: float = 0.0
    retrieval_recall_at_5: float = 0.0
    citation_precision: float = 0.0
    citation_recall: float = 0.0
    citation_validity: float = 0.0


@dataclass
class ProvenanceBenchReport:
    """Aggregated KPIs across the gold suite and the adversarial suite."""

    questions_evaluated: int
    ps_mean: float
    ps_median: float
    ps_pass_rate: float
    ps_floor: float
    answer_point_recall_mean: float
    retrieval_recall_at_5_mean: float
    citation_precision_mean: float
    citation_recall_mean: float
    citation_validity_rate: float
    question_results: list[QuestionResult]
    adversarial: AdversarialReport

    # v3.2 KPI floors / ceilings.
    ps_target: float = 0.80
    answer_point_recall_target: float = 0.90
    retrieval_recall_at_5_target: float = 0.90
    citation_precision_target: float = 0.90
    citation_recall_target: float = 0.90
    citation_validity_target: float = 1.0
    misled_max: float = 0.10
    hallucination_max: float = 0.10
    distractor_visited_min: float = 0.50

    def all_kpis_pass(self) -> bool:
        return (
            self.ps_mean >= self.ps_target
            and self.answer_point_recall_mean >= self.answer_point_recall_target
            and self.retrieval_recall_at_5_mean >= self.retrieval_recall_at_5_target
            and self.citation_precision_mean >= self.citation_precision_target
            and self.citation_recall_mean >= self.citation_recall_target
            and self.citation_validity_rate >= self.citation_validity_target
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
        cited_chunk_ids = [str(value) for value in out.get("cited_chunk_ids") or []]
        claims = out.get("claims") or []
        pack = out.get("evidence_pack") or {}
        rerank_trace = sorted(
            pack.get("rerank_trace") or [],
            key=lambda row: row.get("post_rerank_rank") or row.get("pre_rerank_rank") or 10**9,
        )
        retrieved_chunk_ids = [
            str(row.get("chunk_id")) for row in rerank_trace if row.get("chunk_id")
        ]
        if not retrieved_chunk_ids:
            retrieved_chunk_ids = [
                str(row.get("chunk_id"))
                for row in pack.get("vector_chunks") or []
                if row.get("chunk_id")
            ]
        answer = str(out.get("answer") or "")
        ps = provenance_sufficiency(
            answer=answer,
            claims=claims,
            cited_chunk_ids=cited_chunk_ids,
            chunk_contents=chunk_contents,
        )
        results.append(
            QuestionResult(
                question_id=q.id,
                question=q.question,
                language=q.language,
                category=q.category,
                provenance=ps,
                cited_chunk_ids=cited_chunk_ids,
                answer=answer,
                expected_chunk_ids=list(q.gold_chunk_ids),
                retrieved_chunk_ids=retrieved_chunk_ids,
                answer_point_recall=answer_point_recall(
                    answer,
                    q.required_answer_points,
                    forbidden_points=q.forbidden_answer_points,
                ),
                retrieval_recall_at_5=retrieval_recall_at_k(
                    retrieved_chunk_ids, q.gold_chunk_ids, k=5
                ),
                citation_precision=citation_precision(cited_chunk_ids, q.gold_chunk_ids),
                citation_recall=citation_recall(cited_chunk_ids, q.gold_chunk_ids),
                citation_validity=citation_validity(
                    cited_chunk_ids=cited_chunk_ids,
                    retrieved_chunk_ids=retrieved_chunk_ids,
                    claims=claims,
                ),
            )
        )

    ps_scores = [r.provenance.score for r in results] or [0.0]
    ps_mean = round(statistics.fmean(ps_scores), 4)
    ps_median = round(statistics.median(ps_scores), 4)
    ps_pass_rate = round(sum(1 for s in ps_scores if s >= ps_floor) / len(ps_scores), 4)
    answer_recall_mean = (
        round(statistics.fmean(r.answer_point_recall for r in results), 4) if results else 0.0
    )
    retrieval_recall_mean = (
        round(statistics.fmean(r.retrieval_recall_at_5 for r in results), 4) if results else 0.0
    )
    citation_precision_mean = (
        round(statistics.fmean(r.citation_precision for r in results), 4) if results else 0.0
    )
    citation_recall_mean = (
        round(statistics.fmean(r.citation_recall for r in results), 4) if results else 0.0
    )
    citation_validity_rate = (
        round(statistics.fmean(r.citation_validity for r in results), 4) if results else 0.0
    )

    adv_report = run_adversarial(ds, adv_orch)

    return ProvenanceBenchReport(
        questions_evaluated=len(results),
        ps_mean=ps_mean,
        ps_median=ps_median,
        ps_pass_rate=ps_pass_rate,
        ps_floor=ps_floor,
        answer_point_recall_mean=answer_recall_mean,
        retrieval_recall_at_5_mean=retrieval_recall_mean,
        citation_precision_mean=citation_precision_mean,
        citation_recall_mean=citation_recall_mean,
        citation_validity_rate=citation_validity_rate,
        question_results=results,
        adversarial=adv_report,
    )
