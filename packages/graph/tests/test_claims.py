"""Sentence-level claim model + heuristics."""

from __future__ import annotations

import json

from graphrag_graph.claims import (
    Claim,
    coerce_claims,
    heuristic_claims,
    split_into_claims,
)


def test_split_handles_zh_and_en_punctuation():
    text = "GraphRAG 是一种检索增强生成。It uses Neo4j. Does it work? Yes!"
    parts = split_into_claims(text)
    assert len(parts) == 4
    assert parts[0].startswith("GraphRAG")
    assert parts[2].endswith("work?")


def test_split_preserves_code_fence():
    text = "First sentence. ```python\nprint('hi.')\nprint('bye?')\n``` Third sentence."
    parts = split_into_claims(text)
    # The code block must remain one undivided span.
    assert any(p.startswith("```") and "print('hi.')" in p and "print('bye?')" in p for p in parts)


def test_split_preserves_display_math():
    text = "Equation follows. $$a^2 + b^2 = c^2.$$ Done."
    parts = split_into_claims(text)
    assert any(p.startswith("$$") and p.endswith("$$") for p in parts)


def test_coerce_claims_accepts_dicts():
    raw = [
        {"text": "Sentence A.", "evidence_ids": ["c1"], "support": "supported"},
        {"text": "Sentence B.", "evidence_ids": [], "support": "unsupported"},
    ]
    claims = coerce_claims(raw)
    assert len(claims) == 2
    assert claims[0].is_supported() is True
    assert claims[1].is_supported() is False


def test_coerce_claims_accepts_json_string():
    raw = json.dumps([{"text": "X.", "evidence_ids": ["c1"], "support": "supported"}])
    claims = coerce_claims(raw)
    assert claims[0].text == "X."
    assert claims[0].evidence_ids == ["c1"]


def test_coerce_claims_accepts_strings_and_marks_unsupported():
    claims = coerce_claims(["foo.", "bar."])
    assert all(isinstance(c, Claim) for c in claims)
    assert all(c.support == "unsupported" for c in claims)


def test_heuristic_claims_matches_via_token_overlap():
    contexts = [
        {
            "chunk_id": "c1",
            "content": "GraphRAG combines vector retrieval and knowledge graph traversal.",
        },
        {"chunk_id": "c2", "content": "Neo4j is a graph database queried by Cypher."},
    ]
    answer = (
        "GraphRAG combines vector retrieval and knowledge graph traversal."
        " Neo4j stores the knowledge graph for GraphRAG."
    )
    claims = heuristic_claims(
        answer,
        cited_chunk_ids=["c1", "c2"],
        contexts=contexts,
    )
    assert len(claims) == 2
    # First sentence overlaps heavily with c1 — must include c1.
    assert "c1" in claims[0].evidence_ids
    # Second sentence mentions Neo4j + knowledge graph — should include c2.
    assert "c2" in claims[1].evidence_ids


def test_heuristic_claims_falls_back_when_no_contexts():
    claims = heuristic_claims(
        "Sentence one. Sentence two.",
        cited_chunk_ids=["c1"],
        contexts=None,
    )
    assert len(claims) == 2
    assert all(c.evidence_ids == ["c1"] for c in claims)
    assert all(c.support == "supported" for c in claims)
