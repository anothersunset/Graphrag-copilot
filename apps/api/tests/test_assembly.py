"""End-to-end: index a corpus → assemble orchestrator → local + global query."""

from __future__ import annotations

from graphrag_api.assembly import build_orchestrator_from_index
from graphrag_graph import GraphConfig, initial_state
from graphrag_kg import build_index
from graphrag_kg.pipeline import Chunk

CORPUS = [
    Chunk("c1", "GraphRAG 使用 Neo4j 存储知识图谱。Neo4j 通过 Cypher 查询语言访问。"),
    Chunk("c2", "GraphRAG 结合向量检索与图谱检索。向量检索依赖 embedding 模型。"),
    Chunk("c3", "BM25 是稀疏检索算法。BM25 依赖关键词匹配。jieba 负责中文分词。"),
    Chunk("c4", "社区检测使用 Louvain 算法。Louvain 通过模块度优化划分社区。"),
]


class EchoLLM:
    """Deterministic LLM stub: answers by echoing the evidence it received."""

    def complete(self, *, model, system, user, timeout_s=30.0):
        # cite the first evidence chunk so the auditor has something to bind
        return "根据证据，答案如下 [chunk:1]。"


def _index():
    return build_index(CORPUS)  # offline co-occurrence + template summaries


def test_local_query_routes_through_ppr():
    orch = build_orchestrator_from_index(_index(), llm_client=EchoLLM())
    state = orch.invoke(initial_state("Neo4j 用什么查询语言?"))
    assert state["plan"]["mode"] == "local"
    tools = {tc["tool"] for tc in state["tool_calls"]}
    assert "retrieve_kg" in tools
    assert "retrieve_kg_global" not in tools
    assert state["answer"]


def test_global_query_routes_through_community_reports():
    orch = build_orchestrator_from_index(_index(), llm_client=EchoLLM())
    state = orch.invoke(initial_state("总结一下这个知识库的主要主题"))
    assert state["plan"]["mode"] == "global"
    tools = {tc["tool"] for tc in state["tool_calls"]}
    assert "retrieve_kg_global" in tools


def test_evidence_pack_flows_end_to_end():
    orch = build_orchestrator_from_index(_index(), llm_client=EchoLLM())
    state = orch.invoke(initial_state("GraphRAG 和 Neo4j 是什么关系?"))
    pack = state.get("evidence_pack")
    assert pack is not None
    # KG route produced graph structure that survived into the pack
    assert pack["visited_nodes"] or pack["graph_paths"]
    assert "cited_chunk_ids" in state


def test_global_search_disabled_when_no_communities():
    index = build_index(CORPUS, detect_communities_=False)
    orch = build_orchestrator_from_index(index, llm_client=EchoLLM())
    state = orch.invoke(initial_state("总结主要主题"))
    tools = {tc["tool"] for tc in state["tool_calls"]}
    # no community reports → global route is suppressed, chunk routes used
    assert "retrieve_kg_global" not in tools


def test_config_override_is_respected():
    cfg = GraphConfig(enable_global_search=False, max_rewrites=1)
    orch = build_orchestrator_from_index(_index(), config=cfg, llm_client=EchoLLM())
    state = orch.invoke(initial_state("总结所有文档的主题"))
    tools = {tc["tool"] for tc in state["tool_calls"]}
    assert "retrieve_kg_global" not in tools
