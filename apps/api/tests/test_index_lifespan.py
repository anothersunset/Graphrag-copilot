"""Lifespan index resolution: prebuilt artifact > corpus rebuild."""

from __future__ import annotations

from pathlib import Path

import pytest
from graphrag_api import app as app_module
from graphrag_kg import Chunk, build_index, load_index, save_index
from starlette.testclient import TestClient

CORPUS = [Chunk("c1.md", "GraphRAG 使用 Neo4j 存储知识图谱。"), Chunk("c2.md", "BM25 是稀疏检索算法。")]


@pytest.fixture()
def corpus_dir(tmp_path: Path) -> Path:
    d = tmp_path / "corpus"
    d.mkdir()
    for c in CORPUS:
        (d / c.chunk_id).write_text(c.content, encoding="utf-8")
    return d


def test_lifespan_loads_prebuilt_artifact_when_present(tmp_path, corpus_dir, monkeypatch):
    monkeypatch.setattr(app_module.settings, "corpus_path", corpus_dir)
    artifact = tmp_path / "index.json"
    save_index(build_index(CORPUS), artifact)
    monkeypatch.setattr(app_module.settings, "index_path", artifact)

    app = app_module.create_app()
    with TestClient(app) as client:
        body = client.get("/readyz").json()
        assert body["status"] == "ready"
        assert body["dependencies"]["index"]["chunks"] == len(CORPUS)


def test_lifespan_falls_back_to_corpus_and_writes_artifact(tmp_path, corpus_dir, monkeypatch):
    monkeypatch.setattr(app_module.settings, "corpus_path", corpus_dir)
    artifact = tmp_path / "auto" / "index.json"
    monkeypatch.setattr(app_module.settings, "index_path", artifact)
    assert not artifact.exists()

    with TestClient(app_module.create_app()) as client:
        assert client.get("/readyz").json()["status"] == "ready"
    # write-through: the rebuilt index landed on disk for the next boot
    assert artifact.exists()
    restored = load_index(artifact)
    assert restored.stats()["nodes"] > 0


def test_lifespan_bad_artifact_falls_back_to_corpus(tmp_path, corpus_dir, monkeypatch):
    monkeypatch.setattr(app_module.settings, "corpus_path", corpus_dir)
    artifact = tmp_path / "broken.json"
    artifact.write_text('{"version": 999}', encoding="utf-8")
    monkeypatch.setattr(app_module.settings, "index_path", artifact)

    with TestClient(app_module.create_app()) as client:
        assert client.get("/readyz").json()["status"] == "ready"
