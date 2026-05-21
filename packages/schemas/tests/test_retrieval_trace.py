"""Tests for the schema invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pydantic
import pytest
from graphrag_schemas import (
    CRAGBranch,
    CRAGDecision,
    RetrievalStep,
    RetrievalTrace,
    RetrieverKind,
    ToolKind,
    ToolSpec,
)


@pytest.fixture
def trace_id():
    return uuid4()


@pytest.fixture
def now():
    return datetime.now(UTC)


def test_retrieval_step_immutable(trace_id, now):
    step = RetrievalStep(
        parent_trace_id=trace_id,
        retriever=RetrieverKind.VECTOR,
        query="test",
        top_k=5,
        started_at=now,
        finished_at=now + timedelta(milliseconds=120),
        latency_ms=120.0,
    )
    with pytest.raises((TypeError, pydantic.ValidationError)):
        step.query = "mutated"  # type: ignore[misc]


def test_retrieval_trace_completeness_invariant(trace_id, now):
    step = RetrievalStep(
        parent_trace_id=trace_id,
        retriever=RetrieverKind.BM25,
        query="q",
        top_k=10,
        started_at=now,
        finished_at=now + timedelta(milliseconds=50),
        latency_ms=50.0,
    )
    trace = RetrievalTrace(
        trace_id=trace_id,
        session_id=uuid4(),
        user_query="q",
        started_at=now,
        finished_at=now + timedelta(milliseconds=200),
        total_latency_ms=200.0,
        steps=[step],
    )
    assert trace.is_complete


def test_retrieval_trace_rejects_orphan_steps(now):
    """A step whose parent_trace_id != trace.trace_id violates completeness."""
    orphan = RetrievalStep(
        parent_trace_id=uuid4(),
        retriever=RetrieverKind.KG,
        query="q",
        top_k=5,
        started_at=now,
        finished_at=now,
        latency_ms=0.0,
    )
    trace = RetrievalTrace(
        trace_id=uuid4(),
        session_id=uuid4(),
        user_query="q",
        started_at=now,
        finished_at=now,
        total_latency_ms=0.0,
        steps=[orphan],
    )
    assert not trace.is_complete


def test_retrieval_trace_by_retriever(trace_id, now):
    s1 = RetrievalStep(
        parent_trace_id=trace_id,
        retriever=RetrieverKind.VECTOR,
        query="a",
        top_k=5,
        started_at=now,
        finished_at=now,
        latency_ms=10.0,
    )
    s2 = RetrievalStep(
        parent_trace_id=trace_id,
        retriever=RetrieverKind.BM25,
        query="a",
        top_k=5,
        started_at=now,
        finished_at=now,
        latency_ms=15.0,
    )
    trace = RetrievalTrace(
        trace_id=trace_id,
        session_id=uuid4(),
        user_query="a",
        started_at=now,
        finished_at=now,
        total_latency_ms=25.0,
        steps=[s1, s2],
    )
    assert len(trace.by_retriever(RetrieverKind.VECTOR)) == 1
    assert len(trace.by_retriever(RetrieverKind.BM25)) == 1
    assert trace.by_retriever(RetrieverKind.KG) == []


def test_crag_branch_from_score(trace_id):
    high = CRAGDecision.from_score(
        parent_trace_id=trace_id,
        confidence_score=0.85,
        reasoning="strong overlap with query intent",
    )
    assert high.branch is CRAGBranch.USE

    mid = CRAGDecision.from_score(
        parent_trace_id=trace_id,
        confidence_score=0.5,
        reasoning="partial match, retry with rewrite",
        rewrite_count=0,
    )
    assert mid.branch is CRAGBranch.REWRITE

    low = CRAGDecision.from_score(
        parent_trace_id=trace_id,
        confidence_score=0.15,
        reasoning="no relevant docs",
    )
    assert low.branch is CRAGBranch.FALLBACK

    exhausted = CRAGDecision.from_score(
        parent_trace_id=trace_id,
        confidence_score=0.5,
        reasoning="still bad after 2 rewrites",
        rewrite_count=2,
    )
    assert exhausted.branch is CRAGBranch.FALLBACK


def test_tool_spec_name_validation():
    """Tool names must be lowercase snake_case."""
    valid = ToolSpec(
        name="vector_search",
        kind=ToolKind.RETRIEVAL,
        description="Search the vector store for similar documents.",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        output_schema={"type": "object"},
    )
    assert valid.name == "vector_search"

    with pytest.raises(pydantic.ValidationError):
        ToolSpec(
            name="BadName",
            kind=ToolKind.RETRIEVAL,
            description="must be lowercase snake_case",
            input_schema={},
            output_schema={},
        )
