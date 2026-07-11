"""End-to-end bench tests — these are the CI canary for v3.2 KPIs."""

from __future__ import annotations

from dataclasses import replace

from graphrag_eval.bench import GOLD_QUESTIONS, render_markdown, run_bench


def test_bench_runs_end_to_end():
    report = run_bench()
    assert report.questions_evaluated > 0
    assert 0.0 <= report.ps_mean <= 1.0
    assert 0.0 <= report.ps_median <= 1.0
    assert 0.0 <= report.ps_pass_rate <= 1.0
    assert 0.0 <= report.answer_point_recall_mean <= 1.0
    assert 0.0 <= report.retrieval_recall_at_5_mean <= 1.0
    assert 0.0 <= report.citation_precision_mean <= 1.0
    assert 0.0 <= report.citation_recall_mean <= 1.0
    assert 0.0 <= report.citation_validity_rate <= 1.0
    assert len(report.adversarial.cases) > 0


def test_reference_orchestrator_hits_every_v32_kpi():
    """The shipped reference orchestrator must clear every v3.2 floor.

    If anyone breaks the bench plumbing (claims, PS, adversarial
    accounting), this fails before the committed baseline goes stale.
    """
    report = run_bench()
    assert report.ps_mean >= report.ps_target, (
        f"PS mean {report.ps_mean} < target {report.ps_target}"
    )
    assert report.answer_point_recall_mean >= report.answer_point_recall_target
    assert report.retrieval_recall_at_5_mean >= report.retrieval_recall_at_5_target
    assert report.citation_precision_mean >= report.citation_precision_target
    assert report.citation_recall_mean >= report.citation_recall_target
    assert report.citation_validity_rate >= report.citation_validity_target
    assert report.adversarial.misled_rate <= report.misled_max
    assert report.adversarial.hallucination_rate <= report.hallucination_max
    assert report.adversarial.distractor_visited_rate >= report.distractor_visited_min
    assert report.all_kpis_pass()


def test_per_question_ps_clears_floor():
    report = run_bench()
    failing = [r for r in report.question_results if r.provenance.score < report.ps_floor]
    assert not failing, "\n".join(f"{r.question_id}: PS={r.provenance.score:.3f}" for r in failing)


def test_report_renders_markdown_with_kpi_section():
    report = run_bench()
    md = render_markdown(report)
    assert "v3.2 KPI summary" in md
    assert "Provenance Sufficiency" in md
    assert "Retrieval Recall@5" in md
    assert "Citation precision" in md
    assert "Adversarial" in md
    assert "all KPIs pass" in md


def test_report_renders_per_question_row():
    report = run_bench()
    md = render_markdown(report)
    for r in report.question_results:
        assert r.question_id in md


def test_report_renders_per_distractor_row():
    report = run_bench()
    md = render_markdown(report)
    for c in report.adversarial.cases:
        assert c.case_id in md


def test_wrong_gold_contract_cannot_keep_benchmark_green():
    invalid = replace(
        GOLD_QUESTIONS[0],
        gold_chunk_ids=("does-not-exist",),
        required_answer_points=("does-not-exist",),
    )
    report = run_bench(questions=[invalid])
    result = report.question_results[0]
    assert result.answer_point_recall == 0.0
    assert result.retrieval_recall_at_5 == 0.0
    assert result.citation_precision == 0.0
    assert result.citation_recall == 0.0
    assert not report.all_kpis_pass()
