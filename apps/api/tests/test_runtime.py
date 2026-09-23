"""Component factories: offline by default, progressive wiring via settings."""

from __future__ import annotations

from typing import Any

import pytest
from graphrag_api.config import Settings
from graphrag_api.runtime import (
    RuntimeComponents,
    build_llm_client,
    build_runtime_components,
)
from graphrag_retrieval.bm25 import BM25Document, BM25Retriever
from graphrag_retrieval.vector import VectorRetriever


def _settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = dict(
        env="test",
        corpus_path=None,
        api_key=None,
        llm_base_url=None,
        llm_api_key=None,
        llm_model=None,
        qdrant_url=None,
        qdrant_collection="graphrag_chunks",
        embedding_model=None,
        embedding_dim=8,
        embedding_device=None,
        bm25_index_path=None,
        reranker_model=None,
    )
    return Settings(**{**defaults, **overrides})


class FakeEmbedder:
    def embed(self, text: str) -> list[float]:
        return [float(len(text) % 8), 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


def test_offline_defaults_wire_nothing():
    components = build_runtime_components(_settings())
    assert components == RuntimeComponents(notes=components.notes)
    assert components.vector is None
    assert components.bm25 is None
    assert components.reranker is None
    assert components.llm_client is None
    summary = components.summary()
    assert summary == {
        "vector": "off(no qdrant_url/embedder)",
        "bm25": "off(no bm25_index_path)",
        "reranker": "off(no reranker_model)",
        "llm": "off(no llm_base_url/api_key/model)",
    }


def test_vector_route_wires_when_qdrant_and_embedder_present():
    components = build_runtime_components(
        _settings(qdrant_url="http://localhost:6333"), embedder=FakeEmbedder()
    )
    assert isinstance(components.vector, VectorRetriever)
    assert components.vector.collection == "graphrag_chunks"
    assert components.summary()["vector"] == "VectorRetriever"


def test_vector_route_stays_off_without_embedder_and_records_note():
    components = build_runtime_components(_settings(qdrant_url="http://localhost:6333"))
    assert components.vector is None
    assert any("vector route off" in note for note in components.notes)


def test_bm25_route_loads_pickle_when_present(tmp_path):
    bm25 = BM25Retriever()
    bm25.add_many(
        [
            BM25Document(chunk_id="c1", content="GraphRAG 结合向量检索与图谱检索。", metadata={}),
            BM25Document(chunk_id="c2", content="BM25 是稀疏检索算法。", metadata={}),
        ]
    )
    path = tmp_path / "bm25.pkl"
    bm25.save(path)

    components = build_runtime_components(_settings(bm25_index_path=path))
    assert isinstance(components.bm25, BM25Retriever)
    assert len(components.bm25) == 2


def test_bm25_route_records_note_when_pickle_missing(tmp_path):
    missing = tmp_path / "nope.pkl"
    components = build_runtime_components(_settings(bm25_index_path=missing))
    assert components.bm25 is None
    assert any("bm25 route off" in note for note in components.notes)


def test_reranker_off_when_flagembedding_absent():
    from importlib.util import find_spec

    if find_spec("FlagEmbedding") is not None:
        pytest.skip("FlagEmbedding installed; absence cannot be simulated here")
    components = build_runtime_components(
        _settings(reranker_model="BAAI/bge-reranker-v2-m3")
    )
    assert components.reranker is None
    assert any("reranker off" in note for note in components.notes)


def test_llm_needs_all_three_settings():
    assert build_llm_client(_settings(llm_base_url="http://x")) is None
    assert build_llm_client(_settings(llm_base_url="http://x", llm_api_key="k")) is None
    client = build_llm_client(
        _settings(llm_base_url="http://x", llm_api_key="k", llm_model="deepseek-chat")
    )
    assert client is not None
    assert client._model == "deepseek-chat"
