"""End-to-end Provenance Benchmark.

Turns v3.2's machinery (sentence-level claims, Provenance Sufficiency,
adversarial harness) into a single runnable proof that the system
actually clears its KPIs on a fixed zh+en corpus.

Two suites in one bench:

1. **Gold provenance** — 8 zh+en gold questions. For each question, an
   injected orchestrator must produce an answer whose claims map back
   to cited chunks with enough overlap to yield Provenance Sufficiency
   ≥ 0.80.
2. **Adversarial** — 6 distractor cases (single-token swaps that flip a
   key fact). The orchestrator must rank the gold chunk above the
   distractor (``misled_rate`` ≤ 0.10), avoid hallucinating against the
   poisoned context (``hallucination_rate`` ≤ 0.10), and still let the
   distractor surface in ``visited_nodes`` so we can prove it was *seen
   and ignored* rather than *unseen* (``distractor_visited_rate`` ≥
   0.50).

A dependency-free ``reference_orchestrator`` ships in this module so
the bench runs in CI with no LLM, vector DB, or graph DB. Production
runners can be substituted by passing any callable with the same
return shape.

Entry point::

    python -m graphrag_eval.bench --out eval/results/v3.2-provenance-baseline.md
"""
from __future__ import annotations

from .corpus import CORPUS, GRAPH_TRIPLES, CorpusChunk
from .questions import BENCH_DISTRACTORS, GOLD_QUESTIONS, BenchQuestion
from .reference_runner import (
    BenchOrchestrator,
    adversarial_orchestrator_adapter,
    reference_orchestrator,
)
from .report import render_markdown
from .runner import ProvenanceBenchReport, QuestionResult, run_bench

__all__ = [
    "BENCH_DISTRACTORS",
    "BenchOrchestrator",
    "BenchQuestion",
    "CORPUS",
    "CorpusChunk",
    "GOLD_QUESTIONS",
    "GRAPH_TRIPLES",
    "ProvenanceBenchReport",
    "QuestionResult",
    "adversarial_orchestrator_adapter",
    "reference_orchestrator",
    "render_markdown",
    "run_bench",
]
