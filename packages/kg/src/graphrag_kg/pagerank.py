"""Personalized PageRank retrieval over the knowledge-graph index.

HippoRAG (Gutiérrez et al., 2024) frames retrieval as associative
memory: query entities seed a Personalized PageRank walk over the
entity graph, and passages are ranked by the PPR mass of the entities
they mention. Compared to the naive "match entity name → enumerate
paths" approach, PPR:

* rewards chunks connected to the query through *many short weighted
  paths* rather than one lucky name match;
* naturally handles multi-hop questions — mass flows through
  intermediate bridging entities without materializing every path;
* degrades gracefully: unmatched seeds simply contribute no mass.

``PPRRetriever`` implements the async retrieval contract used by
``packages/retrieval`` (``aretrieve``), returning chunk-level hits with
``visited_node_ids`` so EvidencePack keeps the graph trail.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from .graph_store import KnowledgeGraphIndex

logger = logging.getLogger(__name__)

ChunkLookup = Callable[[str], str]

_LATIN_TERM = re.compile(r"\b[A-Za-z][A-Za-z0-9_\-]{1,}\b")


def _default_query_terms(query: str) -> list[str]:
    terms = list(_LATIN_TERM.findall(query))
    try:
        import jieba.posseg as pseg

        terms.extend(
            w for w, flag in pseg.cut(query) if flag.startswith("n") and len(w) >= 2
        )
    except ImportError:
        terms.extend(re.findall(r"[一-鿿]{2,6}", query))
    return list(dict.fromkeys(terms))


def ppr_scores(
    index: KnowledgeGraphIndex,
    seeds: list[str],
    *,
    alpha: float = 0.85,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> dict[str, float]:
    """Personalized PageRank with uniform teleport mass on the seed nodes.

    Weighted power iteration implemented directly (networkx ≥3.5 delegates
    ``pagerank`` to scipy, which would be a heavy dependency for graphs of
    this size). Update rule per iteration::

        p(v) ← (1-α)·s(v) + α·Σ_{u→v} p(u)·w(u,v)/W(u)

    where ``s`` is the seed distribution and ``W(u)`` the weighted degree.
    Dangling mass teleports back to the seeds, so scores stay a proper
    probability distribution.
    """
    g = index.graph
    valid = [s for s in seeds if g.has_node(s)]
    if not valid or g.number_of_edges() == 0:
        return {}

    seed_mass = 1.0 / len(valid)
    teleport = {n: (seed_mass if n in set(valid) else 0.0) for n in g.nodes}
    wdeg = {
        n: sum(g.edges[n, nb].get("weight", 1.0) for nb in g.neighbors(n)) for n in g.nodes
    }

    scores = dict(teleport)
    for _ in range(max_iter):
        nxt = {n: (1.0 - alpha) * teleport[n] for n in g.nodes}
        for n, mass in scores.items():
            if mass == 0.0:
                continue
            if wdeg[n] == 0.0:
                for s in valid:  # dangling node — return mass to seeds
                    nxt[s] += alpha * mass * seed_mass
                continue
            spread = alpha * mass / wdeg[n]
            for nb in g.neighbors(n):
                nxt[nb] += spread * g.edges[n, nb].get("weight", 1.0)
        delta = sum(abs(nxt[n] - scores[n]) for n in g.nodes)
        scores = nxt
        if delta < tol:
            break
    return scores


class PPRRetriever:
    """HippoRAG-style chunk retriever backed by Personalized PageRank."""

    name = "kg"

    def __init__(
        self,
        index: KnowledgeGraphIndex,
        *,
        chunk_lookup: ChunkLookup | None = None,
        ner: Any | None = None,
        alpha: float = 0.85,
        top_nodes: int = 20,
        include_paths: bool = True,
        max_depth: int = 2,
    ) -> None:
        self.index = index
        self._chunk_lookup = chunk_lookup
        self.ner = ner
        self.alpha = alpha
        self.top_nodes = top_nodes
        self.include_paths = include_paths
        self.max_depth = max_depth

    def _seeds(self, query: str) -> list[str]:
        terms = self.ner.extract(query) if self.ner is not None else _default_query_terms(query)
        return self.index.match_entities(list(terms))

    async def aretrieve(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        seeds = self._seeds(query)
        if not seeds:
            return []
        scores = ppr_scores(self.index, seeds, alpha=self.alpha)
        if not scores:
            return []

        ranked_nodes = sorted(scores.items(), key=lambda kv: -kv[1])[: self.top_nodes]
        visited = [n for n, _ in ranked_nodes]

        # Chunk score = sum of PPR mass of the entities grounded in it.
        chunk_scores: dict[str, float] = {}
        chunk_nodes: dict[str, list[str]] = {}
        for node, score in ranked_nodes:
            for cid in self.index.chunk_ids_for(node):
                chunk_scores[cid] = chunk_scores.get(cid, 0.0) + score
                chunk_nodes.setdefault(cid, []).append(node)

        hits: list[dict[str, Any]] = []
        for cid, score in sorted(chunk_scores.items(), key=lambda kv: -kv[1])[:top_k]:
            content = self._chunk_lookup(cid) if self._chunk_lookup else ""
            if not content:
                # No chunk text available — render the grounding entities so
                # the generator still receives usable evidence.
                ents = chunk_nodes.get(cid, [])
                content = "; ".join(
                    f"{n}: {self.index.graph.nodes[n].get('description', '')}".strip(": ")
                    for n in ents[:5]
                )
            hits.append(
                {
                    "chunk_id": cid,
                    "source": "kg",
                    "score": round(score, 6),
                    "content": content,
                    "metadata": {
                        "retriever": "ppr",
                        "seed_entities": seeds,
                        "grounded_entities": chunk_nodes.get(cid, []),
                    },
                    "visited_node_ids": chunk_nodes.get(cid, []),
                }
            )

        # Attach top weighted paths on the best hit so multi-hop structure
        # survives into EvidencePack.graph_paths.
        if hits and self.include_paths:
            paths = self.index.subgraph_paths(seeds, max_depth=self.max_depth, branch_limit=4)
            if paths:
                hits[0]["path"] = paths[0]
            hits[0]["visited_node_ids"] = visited
        return hits
