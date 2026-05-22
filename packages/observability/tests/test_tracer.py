"""Tracer no-op + AuditExporter round-trip."""
from __future__ import annotations

from graphrag_observability.langfuse_tracer import NoopTracer
from graphrag_observability.spans import AuditExporter, NodeSpan


class FakeSpan:
    def __init__(self):
        self.ended = False
        self.updates = []

    def update(self, *, output=None, metadata=None):
        self.updates.append((output, metadata))

    def end(self, *, output=None):
        self.ended = True


class FakeTrace:
    def __init__(self):
        self.spans = []
        self.events = []

    def span(self, *, name, input=None, metadata=None):
        s = FakeSpan()
        self.spans.append((name, input, metadata, s))
        return s

    def event(self, *, name, input=None, metadata=None):
        self.events.append((name, input, metadata))

    def update(self, *, output=None, metadata=None): ...
    def end(self, *, output=None): ...


def test_noop_tracer_never_raises():
    t = NoopTracer()
    trace = t.trace("agent.run", input={"q": "hi"}, metadata={"v": "3.1"})
    span = trace.span("planner")
    span.update(output={"plan": ["a"]})
    span.end(output={"plan": ["a"]})
    trace.event("audit.planner")
    trace.end(output={"answer": "hi"})
    t.flush()


def test_node_span_opens_and_closes():
    trace = FakeTrace()
    with NodeSpan(trace, name="retriever", input={"q": "x"}) as span:
        assert isinstance(span, FakeSpan)
        span.update(output={"hits": 5})
    assert span.ended is True
    assert trace.spans[0][0] == "retriever"


def test_audit_exporter_emits_event_per_entry():
    trace = FakeTrace()
    exporter = AuditExporter(trace)
    exporter.export_all(
        [
            {"node": "planner", "timestamp": "t0", "summary": "plan", "detail": {"k": 1}},
            {"node": "retriever", "timestamp": "t1", "summary": "got 5 hits", "detail": {}},
        ]
    )
    names = [e[0] for e in trace.events]
    assert names == ["audit.planner", "audit.retriever"]
    # detail propagates as metadata
    assert trace.events[0][2] == {"k": 1}
