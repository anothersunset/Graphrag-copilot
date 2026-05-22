"""DSPy auditor module — stubbed module round-trip."""

from __future__ import annotations

from graphrag_graph.dspy_auditor import AuditVerdict, DSPyAuditor


class StubModule:
    def __init__(self, verdict="pass", rationale="looks good", cited=None):
        self._verdict = verdict
        self._rationale = rationale
        self._cited = cited or ["a", "b"]
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return type(
            "R",
            (),
            {
                "verdict": self._verdict,
                "rationale": self._rationale,
                "cited_chunk_ids": self._cited,
            },
        )()


def test_audit_round_trips_module_outputs():
    auditor = DSPyAuditor(module=StubModule(verdict="PASS", cited=["x", "y"]))
    v = auditor.audit(
        question="q",
        contexts=["c1", "c2"],
        draft_answer="a",
        chunk_ids=["x", "y", "z"],
    )
    assert isinstance(v, AuditVerdict)
    assert v.verdict == "pass"
    assert v.cited_chunk_ids == ["x", "y"]


def test_audit_handles_string_cited_field():
    auditor = DSPyAuditor(module=StubModule(cited="a, b, c"))
    v = auditor.audit(question="q", contexts=[], draft_answer="a")
    assert v.cited_chunk_ids == ["a", "b", "c"]


def test_audit_falls_back_when_module_raises():
    class Boom:
        def __call__(self, **_kw):
            raise RuntimeError("boom")

    auditor = DSPyAuditor(module=Boom())
    v = auditor.audit(question="q", contexts=[], draft_answer="a")
    assert v.verdict == "unsupported"
    assert v.cited_chunk_ids == []
