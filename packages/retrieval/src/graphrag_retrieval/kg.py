"""Neo4j knowledge graph retriever.

Given a natural-language query, this retriever extracts likely entity
mentions (via injected NER or a simple noun-phrase fallback), runs a
Cypher subgraph query around each entity, and renders the 1-hop
neighborhood as natural-language hits the generator can cite.
"""
from __future__ import annotations

import logging
from typing import Any, Sequence

from .base import RetrievalHit

logger = logging.getLogger(__name__)

DEFAULT_CYPHER = """
MATCH (e:Entity)
WHERE toLower(e.name) IN $names
OPTIONAL MATCH (e)-[r]-(n)
RETURN e.name AS subject,
       type(r)  AS relation,
       n.name   AS object,
       e.id     AS entity_id,
       coalesce(e.description, '') AS subject_desc,
       coalesce(n.description, '') AS object_desc
LIMIT $limit
"""


class KGRetriever:
    """Async-friendly Cypher subgraph retriever."""

    name = "kg"

    def __init__(
        self,
        *,
        uri: str = "bolt://localhost:7687",
        auth: tuple[str, str] = ("neo4j", "graphrag-copilot"),
        database: str | None = None,
        ner: Any | None = None,
        cypher: str = DEFAULT_CYPHER,
        driver: Any | None = None,
    ) -> None:
        self.uri = uri
        self.auth = auth
        self.database = database
        self.ner = ner
        self.cypher = cypher
        self._driver = driver

    @property
    def driver(self):
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as e:
                raise RuntimeError(
                    "KGRetriever requires the neo4j driver. Install with "
                    "'graphrag-retrieval[kg]'."
                ) from e
            self._driver = GraphDatabase.driver(self.uri, auth=self.auth)
        return self._driver

    def _extract_entities(self, query: str) -> list[str]:
        if self.ner is not None:
            ents = self.ner.extract(query)
            return [e.lower() for e in ents]
        # Fallback: jieba noun-phrase candidates.
        try:
            import jieba.posseg as pseg

            return [
                w.lower()
                for w, flag in pseg.cut(query)
                if flag.startswith("n") and len(w) >= 2
            ]
        except ImportError:
            return [t.lower() for t in query.split() if len(t) >= 2]

    async def aretrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        names = self._extract_entities(query)
        if not names:
            return []
        try:
            with self.driver.session(database=self.database) as session:
                records = list(
                    session.run(self.cypher, names=names, limit=top_k * 4)
                )
        except Exception:
            logger.exception("kg retrieval failed for query=%r", query)
            return []

        hits: list[RetrievalHit] = []
        for i, rec in enumerate(records[: top_k * 4]):
            subject = rec.get("subject") or ""
            relation = rec.get("relation")
            obj = rec.get("object")
            entity_id = rec.get("entity_id")
            if relation and obj:
                content = f"{subject} —[{relation}]→ {obj}"
                desc = rec.get("object_desc") or rec.get("subject_desc") or ""
                if desc:
                    content = f"{content}. {desc}"
            else:
                content = f"{subject}: {rec.get('subject_desc', '')}"
            hits.append(
                {
                    "chunk_id": f"kg:{entity_id or subject}:{i}",
                    "source": "kg",
                    "score": 1.0 / (i + 1),
                    "content": content,
                    "metadata": {
                        "subject": subject,
                        "relation": relation,
                        "object": obj,
                        "entity_id": entity_id,
                    },
                }
            )
        return hits[:top_k]

    @classmethod
    def from_triples(cls, triples: Sequence[tuple[str, str, str]]) -> "_StaticKGRetriever":
        return _StaticKGRetriever(triples)


class _StaticKGRetriever:
    """Test double for KGRetriever — returns canned triples as hits."""

    name = "kg"

    def __init__(self, triples: Sequence[tuple[str, str, str]]) -> None:
        self._triples = list(triples)

    async def aretrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        hits: list[RetrievalHit] = []
        for i, (s, r, o) in enumerate(self._triples[:top_k]):
            hits.append(
                {
                    "chunk_id": f"kg:test:{i}",
                    "source": "kg",
                    "score": 1.0 / (i + 1),
                    "content": f"{s} —[{r}]→ {o}",
                    "metadata": {"subject": s, "relation": r, "object": o},
                }
            )
        return hits
