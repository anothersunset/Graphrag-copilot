"""Response-parsing tests for the eval client (backlog P0-2b).

The parse logic in ``run_query`` maps the v1 /api/query contract onto
QueryResult fields. These tests exercise it offline by stubbing
``requests.post`` — no server, no network.

契约 (orchestrator._format_response):
    sources:   [{content, source, score, chunk_id}, ...]
    citations: [{chunk_id, span, confidence}, ...]
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from eval.graphrag_client import run_query


def _api_response():
    """A response shaped exactly like the v1 orchestrator emits."""
    return {
        "query": "系统的嵌入模型是什么？",
        "answer": "使用 BAAI/bge-small-zh-v1.5，维度 512 [chunk:1]",
        "sources": [
            {
                "content": "嵌入模型配置为 BAAI/bge-small-zh-v1.5，维度 512。",
                "source": "bm25",
                "score": 0.82,
                "chunk_id": "config_all.md#3",
            },
            {
                "content": "向量检索基于 FAISS IndexFlatIP。",
                "source": "vector",
                "score": 0.64,
                "chunk_id": "system_architecture.md#2",
            },
        ],
        "citations": [
            {"chunk_id": "config_all.md#3", "span": "BAAI/bge-small-zh-v1.5", "confidence": 0.9},
        ],
        "confidence": 0.77,
        "crag_decision": "use",
        "auditor_verdict": "pass",
        "trace": {"nodes": ["planner", "retriever", "evaluator", "generator", "auditor"], "audit": []},
    }


def _mock_post(response_dict):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = response_dict
    resp.raise_for_status.return_value = None
    return patch("eval.graphrag_client.requests.post", return_value=resp)


def test_retrieved_ids_read_top_level_chunk_id():
    with _mock_post(_api_response()):
        result = run_query("q", {"vector": True}, base_url="http://test")
    assert result.retrieved_ids == ["config_all.md#3", "system_architecture.md#2"]


def test_citations_read_top_level_citation_list():
    """citations must be chunk ids the answer actually cited, not the
    retrieval route names ("vector"/"bm25") the old code collected."""
    with _mock_post(_api_response()):
        result = run_query("q", {"vector": True}, base_url="http://test")
    assert result.citations == ["config_all.md#3"]


def test_contexts_collected_from_sources():
    with _mock_post(_api_response()):
        result = run_query("q", {"vector": True}, base_url="http://test")
    assert len(result.contexts) == 2
    assert "bge-small-zh" in result.contexts[0]


def test_trace_nodes_langgraph_format():
    with _mock_post(_api_response()):
        result = run_query("q", {"vector": True}, base_url="http://test")
    assert result.trace_nodes == ["planner", "retriever", "evaluator", "generator", "auditor"]
    assert result.crag_decision == "use"


def test_empty_sources_and_citations_degrade_cleanly():
    payload = _api_response()
    payload["sources"] = []
    payload["citations"] = []
    with _mock_post(payload):
        result = run_query("q", {"vector": True}, base_url="http://test")
    assert result.retrieved_ids == []
    assert result.citations == []
    assert result.contexts == []


def test_metadata_chunk_id_still_supported_as_fallback():
    """Older payloads may still carry chunk ids under metadata."""
    payload = _api_response()
    payload["sources"] = [
        {"content": "x", "source": "vector", "score": 0.5, "metadata": {"chunk_id": "old.md#1"}},
    ]
    with _mock_post(payload):
        result = run_query("q", {"vector": True}, base_url="http://test")
    assert result.retrieved_ids == ["old.md#1"]


def test_recall_computes_nonzero_with_fixed_extraction():
    """End-to-end sanity: with the fixed extraction + a gold map, the
    recall metric the whole P0-2 fix targets must be able to exceed 0."""
    from eval.metrics import recall_at_k

    with _mock_post(_api_response()):
        result = run_query("q", {"vector": True}, base_url="http://test")
    gold = ["config_all.md#3", "service_llm.md#0"]
    assert recall_at_k(result.retrieved_ids, gold, k=5) == 0.5
