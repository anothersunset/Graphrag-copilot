"""Stable chunk id derivation for the v1 retriever adapters (backlog P0-2a).

``_stable_chunk_id`` must produce ids that are stable across queries and
shared between the vector and BM25 routes, otherwise Recall@5 / citation
metrics compare mismatched identifiers (the root cause of the always-zero
retrieval metrics — see docs/backlog.md P0-2).
"""

from __future__ import annotations

from app.agents.retriever_adapters import _stable_chunk_id


def _doc(metadata, content=""):
    return {"content": content, "metadata": metadata, "score": 0.5}


def test_explicit_chunk_id_wins():
    doc = _doc({"chunk_id": "custom.md#3", "file_name": "other.md", "chunk_index": 0})
    assert _stable_chunk_id(doc) == "custom.md#3"


def test_derives_file_name_and_index_when_missing():
    doc = _doc({"file_name": "service_bm25.md", "chunk_index": 2})
    assert _stable_chunk_id(doc) == "service_bm25.md#2"


def test_derives_from_stored_file_name_fallback():
    doc = _doc({"stored_file_name": "a1b2c3.md", "chunk_index": 5})
    assert _stable_chunk_id(doc) == "a1b2c3.md#5"


def test_content_digest_when_no_index():
    doc1 = _doc({"file_name": "f.md"}, content="同一段内容")
    doc2 = _doc({"file_name": "f.md"}, content="同一段内容")
    doc3 = _doc({"file_name": "f.md"}, content="不同内容")
    assert _stable_chunk_id(doc1) == _stable_chunk_id(doc2)
    assert _stable_chunk_id(doc1) != _stable_chunk_id(doc3)
    assert _stable_chunk_id(doc1).startswith("f.md#sha-")


def test_missing_metadata_degrades_gracefully():
    doc = _doc(None, content="x")
    assert _stable_chunk_id(doc).startswith("unknown#sha-")


def test_vector_and_bm25_routes_share_id_format():
    """Both adapters stamp ids from the same persisted document set, so a
    chunk found by either route yields the same id (dedup + recall need it)."""
    metadata = {"file_name": "system_architecture.md", "chunk_index": 1}
    vector_hit = _stable_chunk_id(_doc(metadata))
    bm25_hit = _stable_chunk_id(_doc(metadata))
    assert vector_hit == bm25_hit == "system_architecture.md#1"
