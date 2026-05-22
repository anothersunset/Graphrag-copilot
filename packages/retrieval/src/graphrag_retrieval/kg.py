"""Neo4j knowledge graph retriever with multi-hop path preservation.

v3.2: switched from 1-hop OPTIONAL MATCH to variable-length path matching
(``MATCH p=(e:Entity)-[*1..max_depth]-()``) so each hit carries the full
traversed path (node ids + relation types + depth). The retriever also
accumulates ``visited_node_ids`` across the whole query — every node it
touched, even paths that didn't make the top-K.
"""
from __future__ import annotations

import logging
from typing import Any, Sequence

from .base import RetrievalHit

logger = logging.getLogger(__name__)

DEFAULT_CYPHER = """
MATCH (e:Entity)
WHERE toLower(e.name) IN $names
CALL {
    WITH e
    MATCH p = (e)-[*1..$max_depth]-(n)
    RETURN p AS path, length(p) AS depth
    ORDER BY depth ASC
    LIMIT $branch_limit
}
RETURN path, depth
LIMIT $limit
"""


class KGRetriever:
    """Async-friendly multi-hop Cypher subgraph retriever."""

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
        max_depth: int = 2,
        branch_limit: int = 8,
    ) -> None:
        self.uri = uri
        self.auth = auth
        self.database = database
        self.ner = ner
        self.cypher = cypher
        self._driver = driver
        self.max_depth = max_depth
        self.branch_limit = branch_limit

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
                    session.run(
                        self.cypher,
                        names=names,
                        max_depth=self.max_depth,
                        branch_limit=self.branch_limit,
                        limit=top_k * 4,
                    )
                )
        except Exception:
            logger.exception("kg retrieval failed for query=%r", query)
            return []

        visited: set[str] = set()
        hits: list[RetrievalHit] = []
        for i, rec in enumerate(records[: top_k * 4]):
            path_obj = rec.get("path")
            depth = int(rec.get("depth") or 0)
            path_dict = _neo4j_path_to_dict(path_obj, depth)
            if path_dict is None:
                continue
            for n in path_dict["nodes"]:
                visited.add(n["id"])
            rendered = _render_path(path_dict)
            hits.append(
                {
                    "chunk_id": f"kg:{path_dict['nodes'][0]['id']}->...->{path_dict['nodes'][-1]['id']}@d{depth}",
                    "source": "kg",
                    "score": 1.0 / (i + 1),
                    "content": rendered,
                    "metadata": {"depth": depth},
                    "path": path_dict,
                    "visited_node_ids": [n["id"] for n in path_dict["nodes"]],
                }
            )

        # broadcast the full visited set onto the top hit so the
        # caller can aggregate per-query visited_nodes for EvidencePack.
        if hits:
            hits[0]["visited_node_ids"] = sorted(visited)
        return hits[:top_k]

    @classmethod
    def from_paths(
        cls, paths: Sequence[dict], *, visited: Sequence[str] | None = None
    ) -> "_StaticKGRetriever":
        return _StaticKGRetriever(paths, visited=visited)

    # legacy convenience for v3.1 tests that pass (s, r, o) triples
    @classmethod
    def from_triples(cls, triples: Sequence[tuple[str, str, str]]) -> "_StaticKGRetriever":
        paths = []
        for s, r, o in triples:
            paths.append(
                {
                    "nodes": [
                        {"id": s, "name": s, "labels": ["Entity"], "properties": {}},
                        {"id": o, "name": o, "labels": ["Entity"], "properties": {}},
                    ],
                    "rels": [{"source_id": s, "target_id": o, "type": r, "properties": {}}],
                    "depth": 1,
                }
            )
        return _StaticKGRetriever(paths)


class _StaticKGRetriever:
    """Test double for KGRetriever — returns canned paths as hits."""

    name = "kg"

    def __init__(self, paths: Sequence[dict], *, visited: Sequence[str] | None = None) -> None:
        self._paths = list(paths)
        self._visited = list(visited) if visited is not None else None

    async def aretrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        hits: list[RetrievalHit] = []
        all_visited: set[str] = set()
        for i, path in enumerate(self._paths[:top_k]):
            for n in path["nodes"]:
                all_visited.add(n["id"])
            rendered = _render_path(path)
            hits.append(
                {
                    "chunk_id": f"kg:{path['nodes'][0]['id']}->...->{path['nodes'][-1]['id']}@d{path['depth']}",
                    "source": "kg",
                    "score": 1.0 / (i + 1),
                    "content": rendered,
                    "metadata": {"depth": path["depth"]},
                    "path": path,
                    "visited_node_ids": [n["id"] for n in path["nodes"]],
                }
            )
        if hits:
            visited = self._visited if self._visited is not None else sorted(all_visited)
            hits[0]["visited_node_ids"] = list(visited)
        return hits


def _neo4j_path_to_dict(path_obj: Any, depth: int) -> dict | None:
    """Convert a neo4j.graph.Path into our plain-dict representation."""
    if path_obj is None:
        return None
    try:
        nodes = [
            {
                "id": str(n.element_id) if hasattr(n, "element_id") else str(n.get("id", n.get("name", ""))),
                "name": str(n.get("name", "")) if hasattr(n, "get") else "",
                "labels": list(getattr(n, "labels", [])),
                "properties": dict(n) if hasattr(n, "items") else {},
            }
            for n in path_obj.nodes
        ]
        rels = [
            {
                "source_id": str(r.start_node.element_id) if hasattr(r.start_node, "element_id") else "",
                "target_id": str(r.end_node.element_id) if hasattr(r.end_node, "element_id") else "",
                "type": r.type,
                "properties": dict(r) if hasattr(r, "items") else {},
            }
            for r in path_obj.relationships
        ]
        return {"nodes": nodes, "rels": rels, "depth": depth}
    except Exception:
        logger.exception("failed to convert neo4j path")
        return None


def _render_path(path: dict) -> str:
    """Render a path dict as 'A -[REL]-> B -[REL2]-> C'."""
    nodes = path["nodes"]
    rels = path["rels"]
    if not nodes:
        return ""
    out = [nodes[0].get("name") or nodes[0].get("id", "")]
    for i, rel in enumerate(rels):
        nxt = nodes[i + 1]
        out.append(f" —[{rel['type']}]→ ")
        out.append(nxt.get("name") or nxt.get("id", ""))
    return "".join(out)
