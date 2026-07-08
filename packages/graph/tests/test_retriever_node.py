"""Retriever node: async/sync fan-out + EvidencePack assembly (v3.2)."""

from __future__ import annotations

from graphrag_graph.nodes.retriever import retriever_node


class SyncRetriever:
    name = "vector"

    def __init__(self, hits):
        self._hits = hits

    def retrieve(self, query, *, top_k):
        return list(self._hits)[:top_k]


class AsyncKGRetriever:
    name = "kg"

    def __init__(self, hits):
        self._hits = hits

    async def aretrieve(self, query, *, top_k):
        return list(self._hits)[:top_k]


class BrokenRetriever:
    name = "bm25"

    def retrieve(self, query, *, top_k):
        raise RuntimeError("boom")


def _state(tools):
    return {"question": "how does GraphRAG use Neo4j?", "tools_to_call": tools}


def test_mixed_sync_async_fanout_merges_hits():
    vec = SyncRetriever([{"chunk_id": "v1", "source": "vector", "score": 0.9, "content": "vec"}])
    kg = AsyncKGRetriever(
        [
            {
                "chunk_id": "kg1",
                "source": "kg",
                "score": 0.8,
                "content": "GraphRAG →[USES]→ Neo4j",
                "path": {
                    "nodes": [
                        {"id": "GraphRAG", "name": "GraphRAG", "labels": ["Tech"], "properties": {}},
                        {"id": "Neo4j", "name": "Neo4j", "labels": ["Tech"], "properties": {}},
                    ],
                    "rels": [
                        {"source_id": "GraphRAG", "target_id": "Neo4j", "type": "USES", "properties": {}}
                    ],
                    "depth": 1,
                },
                "visited_node_ids": ["GraphRAG", "Neo4j"],
            }
        ]
    )
    out = retriever_node(
        _state(["retrieve_vector", "retrieve_kg"]),
        {"retrievers": {"vector": vec, "kg": kg}, "max_hits": 10, "top_k_after_rerank": 5},
    )
    chunk_ids = {h["chunk_id"] for h in out["hits"]}
    assert chunk_ids == {"v1", "kg1"}
    assert all(tc["ok"] for tc in out["tool_calls"])


def test_evidence_pack_preserves_graph_paths_and_visited_nodes():
    kg = AsyncKGRetriever(
        [
            {
                "chunk_id": "kg1",
                "source": "kg",
                "score": 0.8,
                "content": "GraphRAG →[USES]→ Neo4j",
                "path": {
                    "nodes": [
                        {"id": "GraphRAG", "name": "GraphRAG", "labels": ["Tech"], "properties": {}},
                        {"id": "Neo4j", "name": "Neo4j", "labels": ["Tech"], "properties": {}},
                    ],
                    "rels": [
                        {"source_id": "GraphRAG", "target_id": "Neo4j", "type": "USES", "properties": {}}
                    ],
                    "depth": 1,
                },
                "visited_node_ids": ["GraphRAG", "Neo4j", "Cypher"],
            }
        ]
    )
    out = retriever_node(
        _state(["retrieve_kg"]),
        {"retrievers": {"kg": kg}, "max_hits": 10, "top_k_after_rerank": 5},
    )
    pack = out["evidence_pack"]
    assert pack is not None
    assert len(pack["graph_paths"]) == 1
    assert pack["graph_paths"][0]["depth"] == 1
    node_ids = {n["id"] for n in pack["graph_nodes"]}
    assert {"GraphRAG", "Neo4j"} <= node_ids
    # visited includes a node not in any cited path (Cypher)
    visited_ids = {n["id"] for n in pack["visited_nodes"]}
    assert "Cypher" in visited_ids
    # rerank trace has one row per fused hit
    assert len(pack["rerank_trace"]) == len(out["fused_hits"])


def test_failed_retriever_is_recorded_not_raised():
    out = retriever_node(
        _state(["retrieve_bm25"]),
        {"retrievers": {"bm25": BrokenRetriever()}, "max_hits": 10},
    )
    assert out["hits"] == []
    assert out["tool_calls"][0]["ok"] is False
    assert "RuntimeError" in out["tool_calls"][0]["error"]
