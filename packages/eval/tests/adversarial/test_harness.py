"""Adversarial harness: wiring + boundary behavior."""
from __future__ import annotations

from graphrag_eval.adversarial import AdversarialReport, run_adversarial

from .fixtures import build_cases


def _ideal_orchestrator(question: str, corpus: list[dict]) -> dict:
    """Cites only the gold chunk, claims bind to it, distractor is visited."""
    gold = [c for c in corpus if not c.get("metadata", {}).get("is_distractor")]
    distractor = next(
        (c for c in corpus if c.get("metadata", {}).get("is_distractor")), None
    )
    cited = [gold[0]["chunk_id"]] if gold else []
    claims = [
        {"text": "answer.", "evidence_ids": cited, "support": "supported"}
    ]
    visited = []
    for c in corpus:
        visited.append({"id": c.get("node_id") or c["chunk_id"], "name": c["chunk_id"], "labels": []})
    return {
        "answer": "the right answer.",
        "verdict": "pass",
        "cited_chunk_ids": cited,
        "claims": claims,
        "evidence_pack": {"visited_nodes": visited},
    }


def _misled_orchestrator(question: str, corpus: list[dict]) -> dict:
    distractor = next(
        c for c in corpus if c.get("metadata", {}).get("is_distractor")
    )
    return {
        "answer": "the wrong answer.",
        "verdict": "pass",
        "cited_chunk_ids": [distractor["chunk_id"]],
        "claims": [
            {
                "text": "wrong.",
                "evidence_ids": [distractor["chunk_id"]],
                "support": "supported",
            }
        ],
        "evidence_pack": {
            "visited_nodes": [
                {"id": distractor["node_id"], "name": "distractor", "labels": []}
            ]
        },
    }


def _refusing_orchestrator(question: str, corpus: list[dict]) -> dict:
    return {
        "answer": "don't know.",
        "verdict": "unsupported",
        "cited_chunk_ids": [],
        "claims": [],
        "evidence_pack": {"visited_nodes": []},
    }


def test_ideal_orchestrator_hits_all_targets():
    cases = build_cases()
    report = run_adversarial(cases, _ideal_orchestrator)
    assert isinstance(report, AdversarialReport)
    assert report.misled_rate == 0.0
    assert report.hallucination_rate == 0.0
    assert report.distractor_visited_rate == 1.0
    assert report.passes()


def test_misled_orchestrator_flags_both_failure_modes():
    cases = build_cases()
    report = run_adversarial(cases, _misled_orchestrator)
    assert report.misled_rate == 1.0
    # claim binds to distractor → counted as hallucination
    assert report.hallucination_rate == 1.0
    assert report.distractor_visited_rate == 0.0
    assert not report.passes()


def test_refusing_orchestrator_is_not_misled_but_unsupported():
    cases = build_cases()
    report = run_adversarial(cases, _refusing_orchestrator)
    assert report.misled_rate == 0.0
    assert report.hallucination_rate == 1.0  # verdict=unsupported
    # never saw distractor in visited_nodes
    assert report.distractor_visited_rate == 0.0
    assert not report.passes()


def test_report_serializes_to_dict():
    cases = build_cases()[:2]
    report = run_adversarial(cases, _ideal_orchestrator)
    d = report.to_dict()
    assert set(d.keys()) >= {"misled_rate", "hallucination_rate", "distractor_visited_rate", "cases"}
    assert len(d["cases"]) == 2
    assert all({"case_id", "misled", "hallucinated", "verdict"} <= set(c.keys()) for c in d["cases"])


def test_passes_threshold_boundaries():
    cases = build_cases()
    report = run_adversarial(cases, _ideal_orchestrator)
    # tighten thresholds beyond what an ideal run can deliver
    assert not report.passes(min_distractor_visited=1.01)
    # loosen
    assert report.passes(max_misled=0.0, max_hallucination=0.0, min_distractor_visited=1.0)
