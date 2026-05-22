"""EvidencePack + GraphPath model validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from graphrag_schemas.evidence import (
    ChunkEvidence,
    EvidencePack,
    GraphNode,
    GraphPath,
    GraphRel,
)


def _path(depth: int = 2) -> GraphPath:
    nodes = [GraphNode(id=f"n{i}", name=f"N{i}") for i in range(depth + 1)]
    rels = [
        GraphRel(source_id=f"n{i}", target_id=f"n{i + 1}", type="R")
        for i in range(depth)
    ]
    return GraphPath(nodes=nodes, rels=rels, depth=depth)


def test_path_depth_validation_passes_when_lengths_match():
    p = _path(2)
    assert p.depth == 2
    assert len(p.rels) == 2
    assert len(p.nodes) == 3


def test_path_depth_validation_rejects_mismatch():
    with pytest.raises(ValidationError):
        GraphPath(
            nodes=[GraphNode(id="a"), GraphNode(id="b")],
            rels=[
                GraphRel(source_id="a", target_id="b", type="R"),
                GraphRel(source_id="b", target_id="c", type="R"),
            ],
            depth=1,
        )


def test_evidence_pack_id_helpers():
    pack = EvidencePack(
        vector_chunks=[ChunkEvidence(chunk_id="c1", source="vector", content="x")],
        graph_paths=[_path(1), _path(2)],
        graph_nodes=[GraphNode(id="n0"), GraphNode(id="n1"), GraphNode(id="n2")],
        visited_nodes=[GraphNode(id="n0"), GraphNode(id="n9")],
    )
    assert pack.chunk_ids() == ["c1"]
    assert pack.node_ids() == ["n0", "n1", "n2"]
    pids = pack.path_ids()
    assert pids == ["n0->n1@d1", "n0->n1->n2@d2"]


def test_evidence_pack_defaults_are_empty():
    pack = EvidencePack()
    assert pack.vector_chunks == []
    assert pack.graph_paths == []
    assert pack.visited_nodes == []
    assert pack.rerank_trace == []
