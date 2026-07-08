"""In-memory knowledge-graph index over networkx.

This is the substrate the whole GraphRAG index layer operates on:
extraction/resolution feed it, community detection and Personalized
PageRank read it. Neo4j stays an optional *sink* (``to_neo4j_rows``
emits rows the v1 ``kg_service.ingest_knowledge`` UNWIND-batch accepts)
— graph analytics happen here, not in Cypher, so the pipeline runs and
tests without any external service.

Node attributes: ``type`` / ``description`` / ``confidence`` /
``chunk_ids`` (provenance) / ``aliases``.
Edge attributes: ``types`` (relation-type set) / ``weight`` (accumulated
confidence — repeated evidence strengthens the edge) / ``chunk_ids``.
"""

from __future__ import annotations

from collections import deque
from itertools import pairwise
from typing import Any

import networkx as nx

from .models import ExtractionResult
from .resolution import normalize_name


class KnowledgeGraphIndex:
    def __init__(self) -> None:
        self.graph: nx.Graph = nx.Graph()
        # normalized surface form (name or alias) → canonical node id
        self._alias_map: dict[str, str] = {}

    # -- build ------------------------------------------------------------
    def add(self, result: ExtractionResult) -> None:
        for e in result.entities:
            if not e.name:
                continue
            if self.graph.has_node(e.name):
                data = self.graph.nodes[e.name]
                data["confidence"] = max(data.get("confidence", 0.0), e.confidence)
                if e.description and e.description not in data.get("description", ""):
                    data["description"] = (data.get("description", "") + " " + e.description).strip()
                for c in e.source_chunk_ids:
                    if c not in data["chunk_ids"]:
                        data["chunk_ids"].append(c)
                for a in e.aliases:
                    if a not in data["aliases"]:
                        data["aliases"].append(a)
            else:
                self.graph.add_node(
                    e.name,
                    type=e.type,
                    description=e.description,
                    confidence=e.confidence,
                    chunk_ids=list(e.source_chunk_ids),
                    aliases=list(e.aliases),
                )
            self._alias_map[normalize_name(e.name)] = e.name
            for a in e.aliases:
                self._alias_map[normalize_name(a)] = e.name

        for r in result.relations:
            src = self.resolve_name(r.source) or r.source
            tgt = self.resolve_name(r.target) or r.target
            if src == tgt:
                continue
            for n in (src, tgt):
                if not self.graph.has_node(n):
                    self.graph.add_node(
                        n, type="Entity", description="", confidence=r.confidence,
                        chunk_ids=list(r.source_chunk_ids), aliases=[],
                    )
                    self._alias_map[normalize_name(n)] = n
            if self.graph.has_edge(src, tgt):
                data = self.graph.edges[src, tgt]
                data["weight"] += r.confidence
                data["types"].add(r.type)
                for c in r.source_chunk_ids:
                    if c not in data["chunk_ids"]:
                        data["chunk_ids"].append(c)
            else:
                self.graph.add_edge(
                    src, tgt,
                    weight=r.confidence,
                    types={r.type},
                    chunk_ids=list(r.source_chunk_ids),
                )

    # -- lookup -----------------------------------------------------------
    def resolve_name(self, surface: str) -> str | None:
        """Map any surface form (name / alias / different casing) to a node id."""
        return self._alias_map.get(normalize_name(surface))

    def match_entities(self, terms: list[str]) -> list[str]:
        """Resolve query terms to node ids; exact alias hits first, then
        substring containment as a low-cost fuzzy tier."""
        found: dict[str, None] = {}
        norm_terms = [normalize_name(t) for t in terms if t.strip()]
        for t in norm_terms:
            node = self._alias_map.get(t)
            if node:
                found.setdefault(node, None)
        if not found:
            for t in norm_terms:
                if len(t) < 2:
                    continue
                for surface, node in self._alias_map.items():
                    if t in surface or surface in t:
                        found.setdefault(node, None)
        return list(found)

    def chunk_ids_for(self, node: str) -> list[str]:
        if not self.graph.has_node(node):
            return []
        return list(self.graph.nodes[node].get("chunk_ids", []))

    # -- traversal ----------------------------------------------------------
    def subgraph_paths(
        self, seeds: list[str], *, max_depth: int = 2, branch_limit: int = 8
    ) -> list[dict[str, Any]]:
        """BFS paths from each seed, shaped like the retrieval-layer path dicts
        (``nodes`` / ``rels`` / ``depth``) so they flow into EvidencePack as-is."""
        paths: list[dict[str, Any]] = []
        for seed in seeds:
            node = self.resolve_name(seed) or seed
            if not self.graph.has_node(node):
                continue
            emitted = 0
            queue: deque[list[str]] = deque([[node]])
            while queue and emitted < branch_limit:
                path = queue.popleft()
                tail = path[-1]
                neighbors = sorted(
                    self.graph.neighbors(tail),
                    key=lambda n: -self.graph.edges[tail, n]["weight"],
                )
                for nb in neighbors:
                    if nb in path:
                        continue
                    new_path = [*path, nb]
                    paths.append(self._render_path(new_path))
                    emitted += 1
                    if emitted >= branch_limit:
                        break
                    if len(new_path) - 1 < max_depth:
                        queue.append(new_path)
        return paths

    def _render_path(self, node_path: list[str]) -> dict[str, Any]:
        nodes = [
            {
                "id": n,
                "name": n,
                "labels": [self.graph.nodes[n].get("type", "Entity")],
                "properties": {},
            }
            for n in node_path
        ]
        rels = []
        for a, b in pairwise(node_path):
            data = self.graph.edges[a, b]
            rels.append(
                {
                    "source_id": a,
                    "target_id": b,
                    "type": sorted(data["types"])[0],
                    "properties": {"weight": round(data["weight"], 3)},
                }
            )
        return {"nodes": nodes, "rels": rels, "depth": len(rels)}

    # -- export -------------------------------------------------------------
    def to_neo4j_rows(self) -> tuple[list[dict], list[dict]]:
        """Rows compatible with v1 ``kg_service.ingest_knowledge``."""
        entities = [
            {
                "name": n,
                "type": d.get("type", "Entity"),
                "confidence": d.get("confidence", 0.8),
                "properties": {
                    "description": d.get("description", ""),
                    "aliases": list(d.get("aliases", [])),
                    "chunk_ids": list(d.get("chunk_ids", [])),
                },
            }
            for n, d in self.graph.nodes(data=True)
        ]
        relations = [
            {
                "source": a,
                "target": b,
                "type": sorted(d["types"])[0],
                "properties": {"weight": d["weight"], "chunk_ids": list(d["chunk_ids"])},
            }
            for a, b, d in self.graph.edges(data=True)
        ]
        return entities, relations

    def stats(self) -> dict[str, int]:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "aliases": len(self._alias_map),
        }
