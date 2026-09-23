"""Ingest CLI: fine-chunk → KG → Qdrant/BM25 artifacts, with test doubles."""

from __future__ import annotations

import json

from graphrag_api.ingest import fine_chunks, point_id_for, run_ingest
from graphrag_kg import Chunk

DIM = 8


class FakeEmbedder:
    """Deterministic 8-dim embedder: bag-of-charcode buckets."""

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for ch in text[:64]:
            vec[ord(ch) % DIM] += 1.0
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class FakeQdrant:
    def __init__(self) -> None:
        self.collections: dict[str, int] = {}
        self.points: dict[str, dict] = {}

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, collection_name: str, vectors_config) -> None:
        self.collections[collection_name] = vectors_config.size

    def upsert(self, collection_name: str, points: list) -> None:
        for point in points:
            self.points[point.id] = point.payload


CORPUS = [
    Chunk(
        "doc1.md",
        "GraphRAG 使用 Neo4j 存储知识图谱。Neo4j 通过 Cypher 查询语言访问。"
        "向量检索依赖 embedding 模型。BM25 是稀疏检索算法，依赖关键词匹配。",
    ),
    Chunk(
        "doc2.md",
        "社区检测使用 Louvain 算法。Louvain 通过模块度优化划分社区。"
        "Personalized PageRank 支持局部检索。",
    ),
]


def test_fine_chunks_split_documents():
    chunks = fine_chunks(CORPUS, max_tokens=24, overlap_tokens=0)
    assert len(chunks) > len(CORPUS)
    assert all("#" in c.chunk_id or ":" in c.chunk_id for c in chunks)
    assert all(c.content.strip() for c in chunks)


def test_point_id_is_deterministic():
    assert point_id_for("doc.md:0:abc") == point_id_for("doc.md:0:abc")
    assert point_id_for("a") != point_id_for("b")


def test_run_ingest_provisions_all_artifacts(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc1.md").write_text(CORPUS[0].content, encoding="utf-8")
    (corpus / "doc2.md").write_text(CORPUS[1].content, encoding="utf-8")
    out_dir = tmp_path / "index"

    qdrant = FakeQdrant()
    report = run_ingest(
        corpus,
        out_dir,
        embedder=FakeEmbedder(),
        qdrant=qdrant,
        qdrant_collection="test_chunks",
        embedding_dim=DIM,
    )

    assert report.docs == 2
    assert report.chunks >= 2
    assert report.qdrant_points == report.chunks
    assert report.qdrant_collection == "test_chunks"
    assert report.bm25_docs == report.chunks
    assert report.kg_stats["nodes"] > 0
    assert not report.neo4j_exported

    # artifacts exist and are loadable/consumable
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["chunks"] == report.chunks
    assert manifest["embedding_dim"] == DIM
    rows = [
        json.loads(line)
        for line in (out_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == report.chunks
    assert {row["chunk_id"] for row in rows} == set(qdrant_chunk_ids(qdrant))
    assert (out_dir / "bm25.pkl").exists()


def qdrant_chunk_ids(qdrant: FakeQdrant) -> list[str]:
    return [payload["chunk_id"] for payload in qdrant.points.values()]


def test_run_ingest_reingest_overwrites_same_points(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc1.md").write_text(CORPUS[0].content, encoding="utf-8")

    qdrant = FakeQdrant()
    embedder = FakeEmbedder()
    run_ingest(
        corpus,
        tmp_path / "index",
        embedder=embedder,
        qdrant=qdrant,
        qdrant_collection="test_chunks",
        embedding_dim=DIM,
    )
    ids_first = set(qdrant.points)
    run_ingest(
        corpus,
        tmp_path / "index",
        embedder=embedder,
        qdrant=qdrant,
        qdrant_collection="test_chunks",
        embedding_dim=DIM,
    )
    assert set(qdrant.points) == ids_first  # deterministic ids → no duplicates


def test_run_ingest_without_embedder_skips_qdrant_but_writes_bm25(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "doc1.md").write_text(CORPUS[0].content, encoding="utf-8")
    out_dir = tmp_path / "index"

    report = run_ingest(corpus, out_dir)
    assert report.qdrant_points == 0
    assert report.bm25_docs == report.chunks
    assert (out_dir / "bm25.pkl").exists()
    assert (out_dir / "chunks.jsonl").exists()
