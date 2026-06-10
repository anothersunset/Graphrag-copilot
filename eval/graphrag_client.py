"""GraphRAG Copilot 评测客户端.

职责: 封装被测系统 API，调用 7 节点 Agentic RAG，返回结构化 QueryResult。
config 由 ablation 注入: vector/bm25/graph/contextual/crag/verifier/auditor 开关。
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests


@dataclass
class GoldCase:
    """Gold 标准评测用例."""
    id: str
    type: str          # factual|relational|multihop|crossdoc|boundary
    difficulty: str    # easy|medium|hard
    question: str
    gold_answer: str
    gold_answer_points: List[str]
    gold_context_ids: List[str]
    supporting_entities: List[str] = field(default_factory=list)
    expected_tool_calls: int = 0
    expect_answerable: bool = True


@dataclass
class QueryResult:
    """被测系统返回的结构化结果."""
    answer: str
    contexts: List[str]                     # 检索到的上下文片段
    citations: List[str]                    # 答案中的引用来源
    retrieved_ids: List[str]                # 检索到的 chunk ID 列表
    trace_nodes: List[str]                  # 7 节点执行记录
    crag_decision: str                      # keep|rewrite|fallback
    tool_calls: int                         # 工具调用次数
    latency: float                          # 请求延迟(秒)
    confidence: Optional[float] = None      # 只记录，不进指标
    raw_response: Optional[Dict[str, Any]] = None  # 原始 API 响应


# 默认 API 地址
DEFAULT_BASE_URL = os.getenv("GRAPHRAG_API_URL", "http://localhost:8000")


def run_query(question: str, config: Dict[str, Any], base_url: str = DEFAULT_BASE_URL) -> QueryResult:
    """调用被测 GraphRAG Copilot，返回结构化结果。

    Args:
        question: 用户问题
        config: 消融配置，包含 vector/bm25/graph/contextual/crag/verifier/auditor 开关
        base_url: API 基础地址

    Returns:
        QueryResult 结构化结果

    Raises:
        RuntimeError: API 调用失败
    """
    start_time = time.time()

    # 构造请求 - config 中的开关可以作为 metadata 传递
    payload = {
        "query": question,
        "top_k": config.get("top_k", 10),
    }

    # 添加 metadata 用于后端识别消融配置
    metadata = {}
    for key in ("vector", "bm25", "graph", "contextual", "crag", "verifier", "auditor"):
        if key in config:
            metadata[key] = config[key]
    if metadata:
        payload["metadata"] = metadata

    try:
        resp = requests.post(
            f"{base_url}/api/query",
            json=payload,
            timeout=config.get("timeout", 120),
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"GraphRAG API call failed: {e}") from e

    latency = time.time() - start_time
    data = resp.json()

    # 解析 trace 节点（兼容 LangGraph 和 Legacy 两种格式）
    trace = data.get("trace", {})
    trace_nodes = []

    # LangGraph 格式: trace.nodes = ["planner", "retriever", ...]
    if "nodes" in trace and isinstance(trace["nodes"], list):
        trace_nodes = trace["nodes"]
    else:
        # Legacy 格式: trace.analysis / trace.retrieval / trace.reasoning / trace.verification
        for node_key in ("analysis", "retrieval", "reasoning", "verification"):
            if node_key in trace:
                trace_nodes.append(node_key)

    # 解析 CRAG 决策（优先从 API 响应直接读取）
    crag_decision = data.get("crag_decision", "")
    if not crag_decision or crag_decision == "unknown":
        # 回退: 从 trace 推断
        if trace.get("reasoning", {}).get("limitations"):
            crag_decision = "fallback"
        elif trace.get("analysis", {}).get("query_rewrite") != question:
            crag_decision = "rewrite"
        else:
            crag_decision = "use"

    # 解析 sources 为 contexts 和 citations
    sources = data.get("sources", [])
    contexts = []
    citations = []
    retrieved_ids = []
    for s in sources:
        content = s.get("content", "")
        if content:
            contexts.append(content)
        source = s.get("source", "")
        if source:
            citations.append(source)
        # 尝试从 metadata 获取 chunk_id
        chunk_id = s.get("metadata", {}).get("chunk_id") or s.get("id", "")
        if chunk_id:
            retrieved_ids.append(str(chunk_id))

    return QueryResult(
        answer=data.get("answer", ""),
        contexts=contexts,
        citations=citations,
        retrieved_ids=retrieved_ids,
        trace_nodes=trace_nodes,
        crag_decision=crag_decision,
        tool_calls=len(sources),  # 用 sources 数量近似
        latency=latency,
        confidence=data.get("confidence"),  # 只记录
        raw_response=data,
    )
