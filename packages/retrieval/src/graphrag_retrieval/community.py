"""Community-report retriever — the retrieval half of GraphRAG global search.

Corpus-level sensemaking questions ("这批文档的主要主题是什么?") cannot
be answered by chunk retrieval: no single chunk contains the answer.
Microsoft GraphRAG (Edge et al., 2024) answers them over *community
summaries* produced at index time. This retriever ranks those summaries
(``graphrag_kg.CommunityReport`` rows) against the query and returns the
top reports as evidence hits, so the generator can synthesize a global
answer with the report ids as citations.

Ranking = token overlap over title + summary + member-entity names,
blended with the community's structural ``rank`` (degree mass). Pass an
``embedder`` for semantic ranking when one is available.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Any

from .base import RetrievalHit

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[一-鿿]|[A-Za-z][A-Za-z0-9_\-]+")


def _tokens(s: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(s or "")}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


class CommunityRetriever:
    """Rank community reports for global-mode queries.

    ``reports`` accepts ``graphrag_kg.CommunityReport`` objects or plain
    dicts with the same fields (keeps this package decoupled from the kg
    package at import time).
    """

    # hits are graph-derived evidence; "kg" keeps the Source literal closed.
    name = "kg"

    def __init__(
        self,
        reports: Sequence[Any],
        *,
        embedder: Any | None = None,
        rank_weight: float = 0.3,
        prefer_level: int | None = 0,
    ) -> None:
        self._reports = list(reports)
        self._embedder = embedder
        self.rank_weight = rank_weight
        self.prefer_level = prefer_level
        self._vec_cache: list[list[float]] | None = None

    @staticmethod
    def _field(report: Any, name: str, default: Any = "") -> Any:
        if isinstance(report, dict):
            return report.get(name, default)
        return getattr(report, name, default)

    def _text(self, report: Any) -> str:
        entities = self._field(report, "entity_ids", []) or []
        return " ".join(
            [
                str(self._field(report, "title", "")),
                str(self._field(report, "summary", "")),
                " ".join(map(str, entities)),
            ]
        )

    def _relevance(self, query: str, report: Any, idx: int) -> float:
        if self._embedder is not None:
            try:
                if self._vec_cache is None:
                    self._vec_cache = [self._embedder.embed(self._text(r)) for r in self._reports]
                return _cosine(self._embedder.embed(query), self._vec_cache[idx])
            except Exception:
                logger.exception("community embedder failed; using token overlap")
        q = _tokens(query)
        t = _tokens(self._text(report))
        return len(q & t) / len(q) if q else 0.0

    async def aretrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        if not self._reports:
            return []
        scored: list[tuple[float, Any]] = []
        for idx, report in enumerate(self._reports):
            if self.prefer_level is not None and int(self._field(report, "level", 0)) != self.prefer_level:
                continue
            rel = self._relevance(query, report, idx)
            structural = float(self._field(report, "rank", 0.0))
            score = (1.0 - self.rank_weight) * rel + self.rank_weight * structural
            if score > 0.0:
                scored.append((score, report))
        scored.sort(key=lambda pair: -pair[0])

        hits: list[RetrievalHit] = []
        for score, report in scored[:top_k]:
            cid = str(self._field(report, "community_id", ""))
            title = str(self._field(report, "title", ""))
            summary = str(self._field(report, "summary", ""))
            hits.append(
                {
                    "chunk_id": f"community:{cid}",
                    "source": "kg",
                    "score": round(score, 6),
                    "content": f"[{title}] {summary}".strip(),
                    "metadata": {
                        "retriever": "community",
                        "community_id": cid,
                        "level": int(self._field(report, "level", 0)),
                        "entities": list(self._field(report, "entity_ids", []) or [])[:20],
                        "member_chunk_ids": list(self._field(report, "chunk_ids", []) or []),
                        "rank": float(self._field(report, "rank", 0.0)),
                    },
                    "visited_node_ids": list(self._field(report, "entity_ids", []) or []),
                }
            )
        return hits
