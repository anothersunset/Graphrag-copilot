"""Render a ProvenanceBenchReport as committable Markdown.

The rendered file is what we check in to ``eval/results/`` so the repo
always shows the latest measured KPIs alongside the code that produced
them.
"""
from __future__ import annotations

from .runner import ProvenanceBenchReport


def _fmt(x: float) -> str:
    return f"{x:.4f}"


def _check(ok: bool) -> str:
    return "✅" if ok else "❌"


def render_markdown(
    report: ProvenanceBenchReport,
    *,
    title: str = "v3.2 Provenance Baseline",
) -> str:
    adv = report.adversarial
    ps_pass = report.ps_mean >= report.ps_target
    misled_pass = adv.misled_rate <= report.misled_max
    hall_pass = adv.hallucination_rate <= report.hallucination_max
    visited_pass = adv.distractor_visited_rate >= report.distractor_visited_min

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    status = "✅ all KPIs pass" if report.all_kpis_pass() else "❌ one or more KPIs failed"
    lines.append(f"**Status:** {status}")
    lines.append("")

    lines.append("## v3.2 KPI summary")
    lines.append("")
    lines.append("| Metric | Target | Measured | Pass |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| Provenance Sufficiency (mean) | ≥ {report.ps_target:.2f} | "
        f"{_fmt(report.ps_mean)} | {_check(ps_pass)} |"
    )
    lines.append(
        f"| PS pass rate (≥ {report.ps_floor:.2f}) | — | "
        f"{_fmt(report.ps_pass_rate)} | — |"
    )
    lines.append(
        f"| Adversarial misled_rate | ≤ {report.misled_max:.2f} | "
        f"{_fmt(adv.misled_rate)} | {_check(misled_pass)} |"
    )
    lines.append(
        f"| Adversarial hallucination_rate | ≤ {report.hallucination_max:.2f} | "
        f"{_fmt(adv.hallucination_rate)} | {_check(hall_pass)} |"
    )
    lines.append(
        f"| Adversarial distractor_visited_rate | ≥ {report.distractor_visited_min:.2f} | "
        f"{_fmt(adv.distractor_visited_rate)} | {_check(visited_pass)} |"
    )
    lines.append("")

    lines.append("## Gold provenance suite")
    lines.append("")
    lines.append(
        f"Questions evaluated: **{report.questions_evaluated}** · "
        f"PS mean: **{_fmt(report.ps_mean)}** · "
        f"PS median: **{_fmt(report.ps_median)}**"
    )
    lines.append("")
    lines.append("| # | Lang | Category | PS | Recall | Coverage | Cited |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in report.question_results:
        cited = ", ".join(r.cited_chunk_ids[:3]) or "—"
        lines.append(
            f"| `{r.question_id}` | {r.language} | {r.category} | "
            f"{_fmt(r.provenance.score)} | {_fmt(r.provenance.sentence_recall)} | "
            f"{_fmt(r.provenance.coverage)} | {cited} |"
        )
    lines.append("")

    lines.append("## Adversarial suite")
    lines.append("")
    lines.append(f"Cases: **{len(adv.cases)}**")
    lines.append("")
    lines.append("| Case | Not misled | No halluc. | Visited & skipped | Verdict |")
    lines.append("|---|---|---|---|---|")
    for c in adv.cases:
        lines.append(
            f"| `{c.case_id}` | {_check(not c.misled)} | {_check(not c.hallucinated)} | "
            f"{_check(c.distractor_visited_but_skipped)} | {c.verdict} |"
        )
    lines.append("")

    lines.append("## How to regenerate")
    lines.append("")
    lines.append("```bash")
    lines.append(
        "uv run --package graphrag-eval python -m graphrag_eval.bench \\"
    )
    lines.append("    --out eval/results/v3.2-provenance-baseline.md")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)
