"""BM25 retrieval + persistence smoke tests."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from graphrag_retrieval.bm25 import BM25Document, BM25Retriever


DOCS = [
    BM25Document(
        chunk_id="d1",
        content="GraphRAG 是一种结合知识图谱与向量检索的 RAG 变体。",
        metadata={"topic": "intro"},
    ),
    BM25Document(
        chunk_id="d2",
        content="BM25 是一种基于词频的稀疏检索算法。",
        metadata={"topic": "bm25"},
    ),
    BM25Document(
        chunk_id="d3",
        content="知识图谱能够编码实体之间的关系。",
        metadata={"topic": "kg"},
    ),
]


@pytest.fixture
def retriever():
    r = BM25Retriever()
    r.add_many(DOCS)
    r.build()
    return r


def test_retrieves_topic_matching_doc(retriever):
    hits = asyncio.run(retriever.aretrieve("什么是 BM25", top_k=2))
    assert hits, "expected at least one hit"
    assert hits[0]["chunk_id"] == "d2"
    assert hits[0]["source"] == "bm25"
    assert hits[0]["score"] > 0


def test_persistence_roundtrip(retriever, tmp_path: Path):
    path = tmp_path / "bm25.pkl"
    retriever.save(path)
    assert path.exists()
    loaded = BM25Retriever.load(path)
    assert len(loaded) == len(retriever)

    hits_orig = asyncio.run(retriever.aretrieve("知识图谱", top_k=1))
    hits_load = asyncio.run(loaded.aretrieve("知识图谱", top_k=1))
    assert hits_orig[0]["chunk_id"] == hits_load[0]["chunk_id"]


def test_returns_empty_for_empty_corpus():
    empty = BM25Retriever()
    hits = asyncio.run(empty.aretrieve("anything", top_k=5))
    assert hits == []
