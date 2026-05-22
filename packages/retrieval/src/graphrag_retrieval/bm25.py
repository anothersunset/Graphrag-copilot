"""rank_bm25 + jieba sparse retriever with on-disk persistence."""

from __future__ import annotations

import logging
import pickle
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .base import RetrievalHit

logger = logging.getLogger(__name__)


@dataclass
class BM25Document:
    chunk_id: str
    content: str
    metadata: dict


def _tokenize_zh(text: str) -> list[str]:
    """Tokenize CJK text with jieba; fall back to whitespace split if missing."""
    try:
        import jieba

        return [t for t in jieba.lcut(text) if t.strip()]
    except ImportError:
        return [t for t in text.split() if t.strip()]


class BM25Retriever:
    """In-memory BM25 over an injected corpus, with pickle persistence.

    Index is built lazily on first ``aretrieve`` after ``build()``.
    Persistence keeps the tokenized corpus + the BM25 instance.
    """

    name = "bm25"

    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs: list[BM25Document] = []
        self._tokens: list[list[str]] = []
        self._bm25 = None  # rank_bm25.BM25Okapi when built

    # -- corpus management ---------------------------------------------

    def add(self, doc: BM25Document) -> None:
        self._docs.append(doc)
        self._tokens.append(_tokenize_zh(doc.content))
        self._bm25 = None  # invalidate built index

    def add_many(self, docs: Sequence[BM25Document]) -> None:
        for d in docs:
            self.add(d)

    def build(self) -> None:
        from rank_bm25 import BM25Okapi

        if not self._tokens:
            raise ValueError("BM25Retriever has no documents; call add() first")
        self._bm25 = BM25Okapi(self._tokens, k1=self.k1, b=self.b)

    # -- persistence ---------------------------------------------------

    def save(self, path: str | Path) -> None:
        if self._bm25 is None:
            self.build()
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("wb") as f:
            pickle.dump(
                {
                    "k1": self.k1,
                    "b": self.b,
                    "docs": self._docs,
                    "tokens": self._tokens,
                    "bm25": self._bm25,
                },
                f,
            )
        logger.info("BM25Retriever: saved %d docs to %s", len(self._docs), p)

    @classmethod
    def load(cls, path: str | Path) -> BM25Retriever:
        p = Path(path)
        with p.open("rb") as f:
            data = pickle.load(f)
        r = cls(k1=data["k1"], b=data["b"])
        r._docs = data["docs"]
        r._tokens = data["tokens"]
        r._bm25 = data["bm25"]
        logger.info("BM25Retriever: loaded %d docs from %s", len(r._docs), p)
        return r

    # -- retrieval -----------------------------------------------------

    async def aretrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        if self._bm25 is None:
            if not self._tokens:
                return []
            self.build()

        tokens = _tokenize_zh(query)
        scores = self._bm25.get_scores(tokens)

        # argsort descending; cheap for small corpora, swap to heapq.nlargest at scale
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        hits: list[RetrievalHit] = []
        for rank, idx in enumerate(ranked):
            score = float(scores[idx])
            if score <= 0:
                break
            doc = self._docs[idx]
            hits.append(
                {
                    "chunk_id": doc.chunk_id,
                    "source": "bm25",
                    "score": score,
                    "content": doc.content,
                    "metadata": dict(doc.metadata),
                }
            )
        return hits

    def __len__(self) -> int:
        return len(self._docs)
