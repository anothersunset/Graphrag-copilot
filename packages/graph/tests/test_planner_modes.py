"""Planner local/global/hybrid classification + route selection."""

from __future__ import annotations

from graphrag_graph.nodes.planner import classify_query_mode, planner_node


def test_factual_entity_question_is_local():
    assert classify_query_mode("Neo4j 使用什么查询语言?") == "local"
    assert classify_query_mode("What database does GraphRAG use?") == "local"


def test_corpus_sensemaking_question_is_global():
    assert classify_query_mode("总结一下知识库的主要主题") == "global"
    assert classify_query_mode("What are the main themes across all documents?") == "global"


def test_global_cue_plus_entity_is_hybrid():
    # aggregation cue AND a concrete named entity → both route families
    assert classify_query_mode("总结一下 Neo4j 相关的所有内容") == "hybrid"
    assert classify_query_mode("Summarize everything about GraphRAG") == "hybrid"


def test_local_mode_selects_chunk_and_kg_routes():
    # "关系" (relational) is one of the intents that gates retrieve_kg on;
    # plain factual questions ("是什么") deliberately don't need KG lookup.
    out = planner_node({"question": "Neo4j 和 GraphRAG 是什么关系?"}, {"enable_kg": True})
    assert out["plan"]["mode"] == "local"
    assert out["plan"]["intent"] == "relational"
    assert out["tools_to_call"] == ["retrieve_vector", "retrieve_bm25", "retrieve_kg"]
    assert "retrieve_kg_global" not in out["tools_to_call"]


def test_global_mode_selects_community_route():
    out = planner_node({"question": "总结知识库主要主题"}, {"enable_kg": True})
    assert out["plan"]["mode"] == "global"
    assert out["plan"]["intent"] == "summarize"
    assert "retrieve_kg_global" in out["tools_to_call"]
    # global questions don't need chunk routes
    assert "retrieve_vector" not in out["tools_to_call"]


def test_hybrid_mode_selects_all_routes():
    # Global cue ("总结") + entity anchor (Neo4j) → hybrid; relational
    # keyword ("关系") is what gates retrieve_kg on for the local half.
    out = planner_node({"question": "总结一下 Neo4j 和 GraphRAG 的关系"}, {"enable_kg": True})
    assert out["plan"]["mode"] == "hybrid"
    assert "retrieve_vector" in out["tools_to_call"]
    assert "retrieve_kg" in out["tools_to_call"]
    assert "retrieve_kg_global" in out["tools_to_call"]


def test_global_mode_falls_back_to_chunks_when_kg_disabled():
    out = planner_node({"question": "总结知识库主要主题"}, {"enable_kg": False})
    # KG disabled → don't retrieve nothing; use chunk routes
    assert out["tools_to_call"] == ["retrieve_vector", "retrieve_bm25"]


def test_injected_planner_client_overrides_heuristic():
    class FakePlanner:
        def classify(self, question: str) -> dict:
            return {"mode": "global"}

    out = planner_node(
        {"question": "Neo4j 用什么查询?"},  # heuristic would say local
        {"enable_kg": True, "planner_client": FakePlanner()},
    )
    assert out["plan"]["mode"] == "global"


def test_planner_client_failure_falls_back_to_heuristic():
    class BrokenPlanner:
        def classify(self, question: str) -> dict:
            raise RuntimeError("llm down")

    out = planner_node(
        {"question": "总结所有文档"},
        {"enable_kg": True, "planner_client": BrokenPlanner()},
    )
    assert out["plan"]["mode"] == "global"  # heuristic recovered
