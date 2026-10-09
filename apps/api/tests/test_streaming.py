"""True SSE streaming: token deltas flow from the LLM through the API."""

from __future__ import annotations

import json

from graphrag_api.app import create_app
from graphrag_api.assembly import build_orchestrator_from_index
from graphrag_kg import Chunk, build_index
from starlette.testclient import TestClient

CORPUS = [
    Chunk("c1", "GraphRAG 使用 Neo4j 存储知识图谱。Neo4j 通过 Cypher 查询语言访问。"),
    Chunk("c2", "GraphRAG 结合向量检索与图谱检索。向量检索依赖 embedding 模型。"),
]


class StreamingEchoLLM:
    """LLM double with a streaming API, echoing a cited two-part answer."""

    def complete(self, *, model, system, user, timeout_s=30.0):
        return "Neo4j 使用 Cypher [chunk:1]。"

    def complete_stream(self, *, model, system, user, timeout_s=60.0):
        yield "Neo4j 使用 "
        yield "Cypher [chunk:1]。"


def _stream_orchestrator():
    return build_orchestrator_from_index(build_index(CORPUS), llm_client=StreamingEchoLLM())


def test_graph_streams_token_custom_events():
    orch = _stream_orchestrator()
    tokens: list[str] = []
    for chunk in orch.invoke(
        {"question": "Neo4j 用什么查询语言?", "top_k": 5}, stream_mode="custom"
    ):
        if isinstance(chunk, dict) and chunk.get("type") == "token":
            tokens.append(chunk["text"])
    assert "".join(tokens) == "Neo4j 使用 Cypher [chunk:1]。"


def test_api_stream_emits_incremental_tokens():
    app = create_app(orchestrator=_stream_orchestrator())
    with TestClient(app) as client, client.stream(
        "POST", "/v1/ask/stream", json={"query": "Neo4j 用什么查询语言?"}
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        events = [json.loads(line[len("data:"):].strip())
                  for line in resp.iter_lines() if line.startswith("data:")]

    types = [e["type"] for e in events]
    assert types[0] == "phase"
    # real streaming: the answer arrives as multiple token events
    token_events = [e for e in events if e["type"] == "token"]
    assert len(token_events) >= 2
    assert "".join(e["text"] for e in token_events).startswith("Neo4j 使用")
    # protocol contract: answer_start before tokens, answer_end + done after
    assert types.index("answer_start") < types.index("token")
    assert types[-2] == "answer_end" and types[-1] == "done"
    done = events[-1]["data"]
    assert done["answer"].startswith("Neo4j 使用")
    assert done["cited_chunk_ids"]
    assert done["run_id"].startswith("run-")


def test_api_stream_skeleton_mode_still_single_token():
    # no LLM wired: nothing streams, the full answer ships as one token
    app = create_app(orchestrator=build_orchestrator_from_index(build_index(CORPUS)))
    with TestClient(app) as client, client.stream(
        "POST", "/v1/ask/stream", json={"query": "总结主要主题"}
    ) as resp:
        events = [json.loads(line[len("data:"):].strip())
                  for line in resp.iter_lines() if line.startswith("data:")]
    types = [e["type"] for e in events]
    assert types.count("token") == 1
    assert types[-1] == "done"
    assert events[-1]["data"]["answer"]
