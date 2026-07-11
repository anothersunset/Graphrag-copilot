from graphrag_api.app import create_app
from starlette.testclient import TestClient


class FakeOrchestrator:
    async def ainvoke(self, payload):
        assert payload["question"]
        return {
            "answer": "GraphRAG uses graph evidence [chunk:1].",
            "auditor_verdict": "pass",
            "crag_score": 0.9,
            "crag_decision": "use",
            "cited_chunk_ids": ["c1"],
            "citations": [{"chunk_id": "c1"}],
            "hits": [{"chunk_id": "c1", "source": "kg", "score": 0.9, "content": "evidence"}],
            "fused_hits": [{"chunk_id": "c1", "source": "kg", "score": 0.9, "content": "evidence"}],
            "audit": [{"node": "auditor", "decision": "pass"}],
            "claims": [{"text": "claim", "evidence_ids": ["c1"], "support": "supported"}],
            "query_rewrites": [],
            "tool_calls": [{"tool": "retrieve_kg", "ok": True}],
            "evidence_pack": {"visited_nodes": ["GraphRAG"]},
        }


def test_ask_run_lookup_and_real_citation_contract() -> None:
    with TestClient(create_app(orchestrator=FakeOrchestrator())) as client:
        ready = client.get("/readyz")
        assert ready.status_code == 200

        response = client.post("/v1/ask", json={"query": "What is GraphRAG?", "top_k": 3})
        assert response.status_code == 200
        body = response.json()
        assert body["run_id"].startswith("run-")
        assert body["cited_chunk_ids"] == ["c1"]
        assert body["sources"][0]["cited"] is True
        assert body["retrieval_trace"][0]["cited"] is True
        assert body["tool_calls"][0]["tool"] == "retrieve_kg"

        stored = client.get(f"/v1/runs/{body['run_id']}")
        assert stored.status_code == 200
        assert stored.json() == body


def test_stream_done_contains_complete_run() -> None:
    with TestClient(create_app(orchestrator=FakeOrchestrator())) as client:
        response = client.post("/v1/ask/stream", json={"query": "q"})
    assert response.status_code == 200
    assert '"type": "phase"' in response.text
    assert '"type": "done"' in response.text
    assert '"retrieval_trace"' in response.text


def test_api_key_and_legacy_deprecation_headers() -> None:
    with TestClient(create_app(orchestrator=FakeOrchestrator(), api_key="secret")) as client:
        assert client.post("/v1/ask", json={"query": "q"}).status_code == 401
        response = client.post(
            "/api/query",
            json={"query": "q"},
            headers={"X-API-Key": "secret"},
        )
    assert response.status_code == 200
    assert response.headers["Deprecation"] == "true"
    assert "Sunset" in response.headers


def test_ask_fails_closed_without_index() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/ask", json={"query": "q"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "not_ready"


def test_corpus_path_builds_real_index_and_orchestrator(tmp_path) -> None:
    (tmp_path / "knowledge.md").write_text(
        "GraphRAG combines graph retrieval with evidence-grounded generation.",
        encoding="utf-8",
    )
    with TestClient(create_app(corpus_path=tmp_path)) as client:
        ready = client.get("/readyz")
        assert ready.status_code == 200
        assert ready.json()["dependencies"]["index"]["chunks"] == 1
        response = client.post("/v1/ask", json={"query": "What is GraphRAG?"})
    assert response.status_code == 200
    assert response.json()["run_id"].startswith("run-")
