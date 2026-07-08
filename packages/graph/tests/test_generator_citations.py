"""Generator citation filtering + fallback language + rewriter reformulation."""

from __future__ import annotations

from graphrag_graph.nodes.fallback import fallback_node
from graphrag_graph.nodes.generator import generator_node
from graphrag_graph.nodes.rewriter import rewriter_node


def _fused():
    return [
        {"chunk_id": "a", "source": "vector", "score": 0.9, "content": "alpha"},
        {"chunk_id": "b", "source": "vector", "score": 0.8, "content": "beta"},
        {"chunk_id": "c", "source": "bm25", "score": 0.7, "content": "gamma"},
    ]


class CitingLLM:
    def complete(self, *, model, system, user, timeout_s=30.0):
        # cites only chunks 1 and 3
        return "Alpha is X [chunk:1]. Gamma is Y [chunk:3]."


def test_citations_restricted_to_cited_markers():
    out = generator_node(
        {"question": "q", "fused_hits": _fused()},
        {"llm_client": CitingLLM()},
    )
    cited = {c["chunk_id"] for c in out["citations"]}
    assert cited == {"a", "c"}  # chunk 2 (b) not cited


def test_skeleton_mode_cites_all_when_no_markers():
    out = generator_node({"question": "q", "fused_hits": _fused()}, {})
    # skeleton answer has no [chunk:N] markers → fall back to all fused
    assert len(out["citations"]) == 3


def test_fallback_answers_in_chinese_for_cjk_question():
    out = fallback_node({"question": "知识库里有什么?", "crag_score": 0.1, "fused_hits": []})
    assert "无法" in out["answer"]
    assert "crag_score" in out["answer"]


def test_fallback_answers_in_english_for_latin_question():
    out = fallback_node({"question": "what is in the KB?", "crag_score": 0.1, "fused_hits": []})
    assert "don't have enough" in out["answer"]


def test_rewriter_condenses_then_expands():
    q = "GraphRAG 是如何使用 Neo4j 来存储知识图谱的?"
    first = rewriter_node({"question": q, "query_rewrites": [], "rewrite_iteration": 0})
    new_q1 = first["query_rewrites"][0]
    # iteration 1: condensed — strips question words, keeps salient terms
    assert new_q1 != q
    assert "如何" not in new_q1
    assert "Neo4j" in new_q1 or "GraphRAG" in new_q1

    second = rewriter_node(
        {"question": q, "query_rewrites": [new_q1], "rewrite_iteration": 1}
    )
    new_q2 = second["query_rewrites"][0]
    # iteration 2: expansion — original question retained + terms appended
    assert q in new_q2
    assert new_q2 != new_q1
    assert second["rewrite_iteration"] == 2


def test_injected_rewriter_takes_precedence():
    class FakeRewriter:
        def rewrite(self, question, *, prior_rewrites):
            return "REWRITTEN"

    out = rewriter_node(
        {"question": "q", "query_rewrites": [], "rewrite_iteration": 0},
        {"query_rewriter": FakeRewriter()},
    )
    assert out["query_rewrites"] == ["REWRITTEN"]
