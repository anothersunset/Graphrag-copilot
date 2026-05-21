"""Adversarial robustness harness.

Replays each test case through an injected orchestrator with a
distractor chunk planted next to the gold corpus, and reports three
metrics:

- ``misled_rate`` — fraction of cases where ``cited_chunk_ids`` includes
  the distractor (the system was fooled).
- ``hallucination_rate`` — fraction of cases where the verdict is in
  ``{hallucination, unsupported}`` OR any claim binds to the
  distractor's id.
- ``distractor_visited_rate`` — fraction of cases where the distractor
  showed up in ``visited_nodes`` (KG layer) but was correctly NOT cited.
  Positive signal: the retriever saw it and the auditor declined it.

The orchestrator is dependency-injected: pass any callable
``orchestrate(question, corpus) -> dict`` so the harness can run in CI
without a real Neo4j / vector DB.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence


@dataclass
class DistractorCase:
    case_id: str
    question: str
    gold_answer: str
    gold_chunks: list[dict]            # list of {chunk_id, content, ...}
    distractor_chunk: dict              # planted lie
    expected_cited_ids: list[str] = field(default_factory=list)


@dataclass
class CaseResult:
    case_id: str
    misled: bool
    hallucinated: bool
    distractor_visited_but_skipped: bool
    verdict: str
    cited_chunk_ids: list[str]
    distractor_id: str


@dataclass
class AdversarialReport:
    misled_rate: float
    hallucination_rate: float
    distractor_visited_rate: float
    cases: list[CaseResult]

    def passes(
        self,
        *,
        max_misled: float = 0.10,
        max_hallucination: float = 0.10,
        min_distractor_visited: float = 0.50,
    ) -> bool:
        return (
            self.misled_rate <= max_misled
            and self.hallucination_rate <= max_hallucination
            and self.distractor_visited_rate >= min_distractor_visited
        )

    def to_dict(self) -> dict:
        return {
            "misled_rate": self.misled_rate,
            "hallucination_rate": self.hallucination_rate,
            "distractor_visited_rate": self.distractor_visited_rate,
            "cases": [
                {
                    "case_id": c.case_id,
                    "misled": c.misled,
                    "hallucinated": c.hallucinated,
                    "distractor_visited_but_skipped": c.distractor_visited_but_skipped,
                    "verdict": c.verdict,
                    "cited_chunk_ids": c.cited_chunk_ids,
                    "distractor_id": c.distractor_id,
                }
                for c in self.cases
            ],
        }


Orchestrator = Callable[[str, list[dict]], dict]


def run_adversarial(
    cases: Sequence[DistractorCase],
    orchestrator: Orchestrator,
) -> AdversarialReport:
    results: list[CaseResult] = []

    for case in cases:
        corpus = list(case.gold_chunks) + [case.distractor_chunk]
        state = orchestrator(case.question, corpus)

        cited = list(state.get("cited_chunk_ids") or [])
        verdict = str(state.get("verdict") or "unsupported").lower()
        claims = state.get("claims") or []
        evidence_pack = state.get("evidence_pack") or {}
        visited = {
            n.get("id") if isinstance(n, dict) else getattr(n, "id", None)
            for n in evidence_pack.get("visited_nodes") or []
        }

        distractor_id = case.distractor_chunk["chunk_id"]
        misled = distractor_id in cited

        claim_touches_distractor = any(
            distractor_id
            in (c.get("evidence_ids", []) if isinstance(c, dict) else getattr(c, "evidence_ids", []))
            for c in claims
        )
        hallucinated = (
            verdict in {"hallucination", "unsupported"} or claim_touches_distractor
        )

        distractor_node_id = case.distractor_chunk.get("node_id") or distractor_id
        visited_but_skipped = (distractor_node_id in visited) and not misled

        results.append(
            CaseResult(
                case_id=case.case_id,
                misled=misled,
                hallucinated=hallucinated,
                distractor_visited_but_skipped=visited_but_skipped,
                verdict=verdict,
                cited_chunk_ids=cited,
                distractor_id=distractor_id,
            )
        )

    n = max(len(results), 1)
    return AdversarialReport(
        misled_rate=round(sum(1 for r in results if r.misled) / n, 4),
        hallucination_rate=round(sum(1 for r in results if r.hallucinated) / n, 4),
        distractor_visited_rate=round(
            sum(1 for r in results if r.distractor_visited_but_skipped) / n, 4
        ),
        cases=results,
    )


def build_distractor(
    *,
    case_id: str,
    gold_chunk: dict,
    swap: tuple[str, str] | None = None,
) -> dict:
    """Generate a distractor by swapping a key token in a gold chunk.

    The result is lexically similar to gold but factually wrong, e.g.::

        gold:      "Neo4j is a graph database queried by Cypher."
        distractor: "Neo4j is a graph database queried by SQL."

    Pass ``swap=("Cypher", "SQL")`` to control the substitution.
    """
    content = gold_chunk.get("content", "")
    if swap is not None:
        content = content.replace(swap[0], swap[1])
    return {
        "chunk_id": f"distractor:{case_id}",
        "node_id": f"distractor:{case_id}:node",
        "source": "vector",
        "content": content,
        "score": 0.85,
        "metadata": {"is_distractor": True, "swap": list(swap) if swap else None},
    }
