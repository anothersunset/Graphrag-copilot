"""EvidencePack and supporting graph-side models.

The EvidencePack replaces the v3.1 ``list[RetrievalHit]`` contract that
retrieval handed to the generator/auditor. It preserves the multi-hop
graph structure that the KG retriever produces — not just the rendered
natural-language hit — so the auditor (and the frontend) can cite a
specific node *or edge* and the eval layer can compute provenance
sufficiency.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Source = Literal["vector", "bm25", "kg", "web"]


class ChunkEvidence(BaseModel):
    """A single retrieved chunk in canonical form."""

    chunk_id: str
    source: Source
    content: str
    score: float = 0.0
    rerank_score: float | None = None
    metadata: dict = Field(default_factory=dict)


class GraphNode(BaseModel):
    """A node returned (or visited) by the KG retriever."""

    id: str
    name: str = ""
    labels: list[str] = Field(default_factory=list)
    properties: dict = Field(default_factory=dict)


class GraphRel(BaseModel):
    """A directed relation between two graph nodes."""

    source_id: str
    target_id: str
    type: str
    properties: dict = Field(default_factory=dict)


class GraphPath(BaseModel):
    """A traversed multi-hop path from the KG retriever."""

    nodes: list[GraphNode]
    rels: list[GraphRel]
    depth: int
    rendered: str = ""  # natural-language rendering used as RetrievalHit.content

    @field_validator("rels")
    @classmethod
    def _rels_match_depth(cls, v: list[GraphRel], info):
        depth = info.data.get("depth")
        if depth is not None and len(v) != depth:
            raise ValueError(f"rels length {len(v)} must equal depth {depth}")
        return v

    @field_validator("nodes")
    @classmethod
    def _nodes_match_depth(cls, v: list[GraphNode], info):
        depth = info.data.get("depth")
        if depth is not None and len(v) != depth + 1:
            raise ValueError(f"nodes length {len(v)} must equal depth+1 ({depth + 1})")
        return v


class RerankTraceRow(BaseModel):
    """One row of the post-fusion rerank trace."""

    chunk_id: str
    pre_rerank_rank: int
    post_rerank_rank: int
    rerank_score: float


class EvidencePack(BaseModel):
    """The full evidence surface handed to the generator and auditor.

    - ``vector_chunks`` and ``graph_paths`` are the *cited candidates*.
    - ``graph_nodes`` is the de-duplicated union of every node that
      appears in any path.
    - ``visited_nodes`` is *everything the KG retriever touched*, even
      paths that didn't make the top-K — this lets the adversarial harness
      detect "the misleading node was seen but correctly ignored".
    - ``rerank_trace`` records how fusion + rerank reshuffled candidates.
    """

    vector_chunks: list[ChunkEvidence] = Field(default_factory=list)
    graph_nodes: list[GraphNode] = Field(default_factory=list)
    graph_paths: list[GraphPath] = Field(default_factory=list)
    visited_nodes: list[GraphNode] = Field(default_factory=list)
    rerank_trace: list[RerankTraceRow] = Field(default_factory=list)

    def chunk_ids(self) -> list[str]:
        return [c.chunk_id for c in self.vector_chunks]

    def node_ids(self) -> list[str]:
        return [n.id for n in self.graph_nodes]

    def path_ids(self) -> list[str]:
        return ["->".join(n.id for n in p.nodes) + f"@d{p.depth}" for p in self.graph_paths]
