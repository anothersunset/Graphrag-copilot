"""Offline ingestion CLI provisioning the real retrieval stack.

    uv run --package graphrag-api python -m graphrag_api.ingest \
        --corpus demo_docs --out-dir data/index

Pipeline: load corpus docs → semantic fine-chunking → build the in-memory
KG (co-occurrence; LLM extraction lands later) → embed + upsert to Qdrant →
persist a BM25 pickle → optionally export the KG to Neo4j. Artifacts:

* ``<out-dir>/chunks.jsonl``  — fine chunks; point ``GRAPHRAG_CORPUS_PATH``
  here so the API's rebuilt KG indexes exactly the same chunks the dense
  and sparse routes serve.
* ``<out-dir>/bm25.pkl``      — set ``GRAPHRAG_BM25_INDEX_PATH`` to this.
* ``<out-dir>/manifest.json`` — what was ingested, with which dim/model.

Known limitation: the KG itself is rebuilt in API memory at startup and not
loaded from this run, so LLM-grade extraction/summaries do not survive a
restart yet.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast

from graphrag_kg import Chunk, build_index
from graphrag_parsers import SemanticChunker

from graphrag_api.config import settings
from graphrag_api.corpus import load_corpus

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
CHUNKS_NAME = "chunks.jsonl"
BM25_NAME = "bm25.pkl"

# Entity/rel names end up in Qdrant payloads and Neo4j MERGE keys; keep the
# JSONL encoding-tolerant by banning only control chars/newlines.
_SANITIZE_RE = re.compile(r"[\x00-\x1f]+")


def point_id_for(chunk_id: str) -> str:
    """Deterministic UUID so re-ingest overwrites instead of duplicating."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"graphrag-chunk:{chunk_id}"))


class QdrantLike(Protocol):
    """Minimal client surface used here (real client or a test double)."""

    def collection_exists(self, collection_name: str) -> bool: ...

    def create_collection(self, collection_name: str, vectors_config: Any) -> None: ...

    def upsert(self, collection_name: str, points: list[Any]) -> Any: ...


class EmbedderLike(Protocol):
    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class IngestReport:
    corpus: str
    docs: int
    chunks: int
    qdrant_points: int = 0
    qdrant_collection: str | None = None
    bm25_docs: int = 0
    kg_stats: dict[str, int] = field(default_factory=dict)
    neo4j_exported: bool = False
    artifacts: dict[str, str] = field(default_factory=dict)


def fine_chunks(docs: list[Chunk], *, max_tokens: int, overlap_tokens: int) -> list[Chunk]:
    """Split document-level chunks into retrieval-sized passages."""
    chunker = SemanticChunker(max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    out: list[Chunk] = []
    for doc in docs:
        doc_id = _SANITIZE_RE.sub(" ", doc.chunk_id).strip()
        for rec in chunker.split(doc_id=doc_id, text=doc.content):
            out.append(Chunk(rec.chunk_id, rec.content))
    return out


def upsert_to_qdrant(
    chunks: list[Chunk],
    *,
    client: QdrantLike,
    collection: str,
    embedder: EmbedderLike,
    dim: int,
) -> int:
    """Embed + upsert all chunks; creates the collection when missing."""
    from qdrant_client.models import Distance, PointStruct, VectorParams

    if not client.collection_exists(collection):
        client.create_collection(
            collection, vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
        )
    vectors = embedder.embed_batch([c.content for c in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("embedder returned a different number of vectors than chunks")
    for vector in vectors:
        if len(vector) != dim:
            raise ValueError(
                f"embedder returned dim {len(vector)} != configured {dim} "
                "(check GRAPHRAG_EMBEDDING_DIM)"
            )
    points = [
        PointStruct(
            id=point_id_for(c.chunk_id),
            vector=vector,
            payload={"chunk_id": c.chunk_id, "content": c.content},
        )
        for c, vector in zip(chunks, vectors, strict=True)
    ]
    # qdrant-client caps batch sizes; 256 is comfortably under the default
    for start in range(0, len(points), 256):
        client.upsert(collection, points[start : start + 256])
    return len(points)


def export_kg_to_neo4j(index: Any, *, uri: str, auth: tuple[str, str]) -> int:
    """MERGE the KG into Neo4j. Fixed ``RELATED`` type with the real label
    kept as a property — relationship types cannot be parameterized in
    Cypher (the exact trap devlog-2026-07-08 records)."""
    from neo4j import GraphDatabase

    entities, relations = index.graph.to_neo4j_rows()
    with GraphDatabase.driver(uri, auth=auth) as driver, driver.session() as session:
            for entity in entities:
                session.run(
                    """
                    MERGE (e:Entity {name: $name})
                    SET e.type = $type, e.confidence = $confidence,
                        e.description = $description, e.aliases = $aliases,
                        e.chunk_ids = $chunk_ids
                    """,
                    **entity,
                )
            for rel in relations:
                session.run(
                    """
                    MATCH (a:Entity {name: $source})
                    MATCH (b:Entity {name: $target})
                    MERGE (a)-[r:RELATED]->(b)
                    SET r.type = $type, r.weight = $weight, r.chunk_ids = $chunk_ids
                    """,
                    **rel,
                )
    return len(relations)


def run_ingest(
    corpus_path: Path,
    out_dir: Path,
    *,
    embedder: EmbedderLike | None = None,
    qdrant: QdrantLike | None = None,
    qdrant_collection: str | None = None,
    embedding_dim: int | None = None,
    neo4j_uri: str | None = None,
    neo4j_auth: tuple[str, str] | None = None,
    max_tokens: int = 512,
    overlap_tokens: int = 64,
) -> IngestReport:
    """Run every provisioning step that has its dependencies available."""
    docs = load_corpus(corpus_path)
    chunks = fine_chunks(docs, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    if not chunks:
        raise ValueError("chunking produced no chunks from a non-empty corpus")

    index = build_index(chunks)

    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = out_dir / CHUNKS_NAME
    chunks_path.write_text(
        "".join(
            json.dumps({"chunk_id": c.chunk_id, "content": c.content}, ensure_ascii=False) + "\n"
            for c in chunks
        ),
        encoding="utf-8",
    )

    report = IngestReport(
        corpus=str(corpus_path),
        docs=len(docs),
        chunks=len(chunks),
        kg_stats=index.stats(),
    )

    collection = qdrant_collection or settings.qdrant_collection
    if embedder is not None and qdrant is not None:
        report.qdrant_points = upsert_to_qdrant(
            chunks,
            client=qdrant,
            collection=collection,
            embedder=embedder,
            dim=embedding_dim if embedding_dim is not None else settings.embedding_dim,
        )
        report.qdrant_collection = collection
    else:
        logger.warning("qdrant step skipped (need --embedder and a Qdrant client)")

    from graphrag_retrieval.bm25 import BM25Document, BM25Retriever

    bm25 = BM25Retriever()
    bm25.add_many(
        [BM25Document(chunk_id=c.chunk_id, content=c.content, metadata={}) for c in chunks]
    )
    bm25_path = out_dir / BM25_NAME
    bm25.save(bm25_path)
    report.bm25_docs = len(bm25)

    if neo4j_uri and neo4j_auth:
        export_kg_to_neo4j(index, uri=neo4j_uri, auth=neo4j_auth)
        report.neo4j_exported = True

    manifest_path = out_dir / MANIFEST_NAME
    report.artifacts = {
        "chunks": str(chunks_path),
        "bm25": str(bm25_path),
        "manifest": str(manifest_path),
    }
    manifest_path.write_text(
        json.dumps(
            {
                **asdict(report),
                "embedding_model": settings.embedding_model,
                "embedding_dim": embedding_dim if embedding_dim is not None else settings.embedding_dim,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("ingest complete: %s", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m graphrag_api.ingest",
        description="Chunk a corpus and provision Qdrant / BM25 / Neo4j artifacts.",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=settings.corpus_path,
        help="Corpus file or directory (default: GRAPHRAG_CORPUS_PATH).",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("data/index"))
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--overlap-tokens", type=int, default=64)
    parser.add_argument(
        "--skip-qdrant",
        action="store_true",
        help="Only write chunks.jsonl + BM25 (no embeddings).",
    )
    parser.add_argument("--neo4j-uri", default=None, help="e.g. bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    if args.corpus is None:
        parser.error("--corpus is required (or set GRAPHRAG_CORPUS_PATH)")
    if args.neo4j_uri and not args.neo4j_password:
        parser.error("--neo4j-password is required with --neo4j-uri")

    embedder = None
    qdrant = None
    if not args.skip_qdrant:
        from graphrag_api.runtime import build_embedder

        embedder = build_embedder(settings)
        if embedder is None:
            logger.warning(
                "no GRAPHRAG_EMBEDDING_MODEL configured; use --skip-qdrant or "
                "configure embeddings"
            )
        elif not settings.qdrant_url:
            logger.warning("no GRAPHRAG_QDRANT_URL configured; skipping Qdrant upsert")
        else:
            from qdrant_client import QdrantClient

            qdrant = cast(QdrantLike, QdrantClient(url=settings.qdrant_url))

    run_ingest(
        args.corpus,
        args.out_dir,
        embedder=embedder,
        qdrant=qdrant,
        neo4j_uri=args.neo4j_uri,
        neo4j_auth=(args.neo4j_user, args.neo4j_password)
        if args.neo4j_uri and args.neo4j_password
        else None,
        max_tokens=args.max_tokens,
        overlap_tokens=args.overlap_tokens,
    )
    print(f"ingested {args.corpus} -> {args.out_dir}")
    print("serve it with:")
    print(f"  GRAPHRAG_CORPUS_PATH={args.out_dir / CHUNKS_NAME}")
    print(f"  GRAPHRAG_BM25_INDEX_PATH={args.out_dir / BM25_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
