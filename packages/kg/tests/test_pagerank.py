"""Personalized PageRank scores + HippoRAG-style chunk retrieval."""

from __future__ import annotations

import pytest
from graphrag_kg.graph_store import KnowledgeGraphIndex
from graphrag_kg.models import EntityRecord, ExtractionResult, RelationRecord
from graphrag_kg.pagerank import PPRRetriever, ppr_scores


def _chain_index() -> KnowledgeGraphIndex:
    """AlphaSys — Bridge — CoreDB chain plus an isolated pair."""
    ents = [
        EntityRecord(name="AlphaSys", type="Technology", source_chunk_ids=["c1"]),
        EntityRecord(name="Bridge", type="Technology", source_chunk_ids=["c1"]),
        EntityRecord(name="CoreDB", type="Technology", source_chunk_ids=["c2"]),
        EntityRecord(name="Island1", type="Technology", source_chunk_ids=["c3"]),
        EntityRecord(name="Island2", type="Technology", source_chunk_ids=["c3"]),
    ]
    rels = [
        RelationRecord(source="AlphaSys", target="Bridge", type="USES", confidence=0.9),
        RelationRecord(source="Bridge", target="CoreDB", type="USES", confidence=0.9),
        RelationRecord(source="Island1", target="Island2", type="USES", confidence=0.9),
    ]
    idx = KnowledgeGraphIndex()
    idx.add(ExtractionResult(entities=ents, relations=rels))
    return idx


def test_ppr_mass_concentrates_near_seed():
    idx = _chain_index()
    scores = ppr_scores(idx, ["AlphaSys"])
    # Mass decays with graph distance from the seed: the seed and the hub
    # it feeds dominate the 2-hop node. (In an undirected chain the degree-2
    # hub can edge past the seed at high alpha — that's correct PPR, so we
    # only assert the distance-decay ordering, not seed-is-max.)
    assert scores["AlphaSys"] > scores["CoreDB"]
    assert scores["Bridge"] > scores["CoreDB"]
    # a lower teleport factor pulls mass back onto the seed itself
    low_alpha = ppr_scores(idx, ["AlphaSys"], alpha=0.5)
    assert low_alpha["AlphaSys"] == max(low_alpha.values())
    # disconnected component receives no seed mass
    assert scores["Island1"] == pytest.approx(0.0, abs=1e-9)
    assert scores["CoreDB"] > scores["Island1"]
    assert sum(scores.values()) == pytest.approx(1.0, abs=1e-6)


def test_ppr_multi_hop_flows_through_bridge():
    """CoreDB is 2 hops from the seed — reachable only through Bridge."""
    idx = _chain_index()
    scores = ppr_scores(idx, ["AlphaSys"])
    assert scores["CoreDB"] > 0.01


def test_ppr_no_valid_seeds_returns_empty():
    idx = _chain_index()
    assert ppr_scores(idx, ["NotInGraph"]) == {}
    assert ppr_scores(KnowledgeGraphIndex(), ["AlphaSys"]) == {}


async def test_ppr_retriever_ranks_seed_chunk_first():
    idx = _chain_index()
    chunk_texts = {"c1": "AlphaSys connects through Bridge.", "c2": "CoreDB stores data.",
                   "c3": "Islands are unrelated."}
    retriever = PPRRetriever(idx, chunk_lookup=chunk_texts.get)
    hits = await retriever.aretrieve("How does AlphaSys work?", top_k=3)

    assert hits, "expected chunk hits"
    assert hits[0]["chunk_id"] == "c1"
    assert hits[0]["source"] == "kg"
    assert hits[0]["content"] == chunk_texts["c1"]
    assert hits[0]["metadata"]["retriever"] == "ppr"
    assert "AlphaSys" in hits[0]["metadata"]["seed_entities"]
    # multi-hop structure survives: top hit carries a path + visited nodes
    assert "path" in hits[0]
    assert "AlphaSys" in hits[0]["visited_node_ids"]
    # 2-hop chunk is reachable but ranked below the seed chunk
    ids = [h["chunk_id"] for h in hits]
    assert "c2" in ids and ids.index("c2") > ids.index("c1")


async def test_ppr_retriever_no_entity_match_returns_empty():
    idx = _chain_index()
    retriever = PPRRetriever(idx)
    assert await retriever.aretrieve("完全无关的问题", top_k=3) == []
