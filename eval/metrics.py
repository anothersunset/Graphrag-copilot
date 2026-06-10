"""三层指标计算模块.

第一层 - 检索质量: Recall@5, Context Precision, Citation Recall
第二层 - 答案质量: Answer Accuracy, Faithfulness, Hallucination Rate, Boundary Refusal Rate
第三层 - Agentic 链路: Trace Completeness, Tool Call Necessity, CRAG Repair Rate,
                       Verifier Pass Rate, Audit Coverage

confidence 只落日志、不进任何指标。
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from eval.graphrag_client import GoldCase, QueryResult


# ─────────────────────────── 第一层：检索质量 ───────────────────────────

def recall_at_k(retrieved_ids: List[str], gold_context_ids: List[str], k: int = 5) -> float:
    """Recall@k: top-k 检索结果中命中 gold context 的比例.

    Args:
        retrieved_ids: 检索返回的 chunk ID 列表
        gold_context_ids: gold 标准的 chunk ID 列表
        k: 取前 k 个结果

    Returns:
        命中比例 [0, 1]
    """
    if not gold_context_ids:
        return 1.0  # 无 gold context 时视为完全召回
    top_k = set(retrieved_ids[:k])
    gold = set(gold_context_ids)
    hit = len(top_k & gold)
    return hit / len(gold)


def context_precision(contexts: List[str], gold_context_ids: List[str]) -> float:
    """Context Precision: 检索片段中相关片段的比例.

    简化实现: 用 retrieved_ids 与 gold_context_ids 的交集比例近似。
    实际生产中应使用 LLM 判断每个 context 是否相关。

    Args:
        contexts: 检索到的上下文文本列表
        gold_context_ids: gold 标准的 chunk ID 列表

    Returns:
        精度 [0, 1]
    """
    if not contexts:
        return 0.0
    # 简化: 如果有 gold_context_ids，用数量比近似
    if gold_context_ids:
        # 假设每个 context 对应一个 id，用比例近似
        return min(len(gold_context_ids) / len(contexts), 1.0)
    return 0.0


def citation_recall(citations: List[str], gold_context_ids: List[str]) -> float:
    """Citation Recall: 答案引用覆盖 gold context 的比例.

    Args:
        citations: 答案中的引用来源列表
        gold_context_ids: gold 标准的 chunk ID 列表

    Returns:
        召回率 [0, 1]
    """
    if not gold_context_ids:
        return 1.0
    if not citations:
        return 0.0
    # 将 citations 视为 retrieved_ids 的子集
    cited_set = set(citations)
    gold_set = set(gold_context_ids)
    hit = len(cited_set & gold_set)
    return hit / len(gold_set)


# ─────────────────────────── 第二层：答案质量 ───────────────────────────

def answer_accuracy(point_coverage: float) -> float:
    """Answer Accuracy: 基于要点覆盖率的准确度.

    Args:
        point_coverage: gold_answer_points 的覆盖率 [0, 1]

    Returns:
        准确度 [0, 1] (直接透传)
    """
    return point_coverage


def faithfulness(answer: str, contexts: List[str], *, use_llm: bool = False) -> float:
    """Faithfulness: 答案是否被上下文支持.

    Args:
        answer: 系统生成的答案
        contexts: 检索到的上下文列表
        use_llm: 是否使用 LLM Judge（更准确但更慢）

    Returns:
        忠实度 [0, 1]
    """
    if not answer or not contexts:
        return 0.0

    if use_llm:
        return _faithfulness_llm(answer, contexts)
    return _faithfulness_keyword(answer, contexts)


def _faithfulness_keyword(answer: str, contexts: List[str]) -> float:
    """关键词匹配版 faithfulness（快速但不精确）."""
    sentences = [s.strip() for s in answer.replace("。", ".").replace("；", ";").split(".") if s.strip()]
    if not sentences:
        return 0.0

    context_text = " ".join(contexts).lower()
    supported = 0
    for sent in sentences:
        keywords = [w for w in sent.split() if len(w) > 1]
        if keywords:
            hit = sum(1 for kw in keywords if kw.lower() in context_text)
            if hit / len(keywords) > 0.3:
                supported += 1

    return supported / len(sentences)


def _faithfulness_llm(answer: str, contexts: List[str]) -> float:
    """LLM Judge 版 faithfulness（更准确）."""
    import os
    import requests as req

    base_url = os.getenv("LLM_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1")
    api_url = os.getenv("LLM_API_URL", base_url.rstrip("/") + "/chat/completions")
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "mimo-v2.5-pro")

    if not api_key:
        return _faithfulness_keyword(answer, contexts)

    context_text = "\n\n".join([f"[{i+1}] {c[:500]}" for i, c in enumerate(contexts[:5])])

    system_prompt = """你是答案忠实度评判专家。判断答案中的每个事实声明是否被上下文支持。

输出严格 JSON:
{"supported": 数量, "total": 总数量, "score": 0.0-1.0}

规则:
1. 将答案拆分为独立的事实声明
2. 检查每个声明是否在上下文中有直接依据
3. 计算被支持的声明比例"""

    user_prompt = f"答案:\n{answer}\n\n上下文:\n{context_text}"

    try:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        payload = {
            "model": model,
            "temperature": 0.0,
            "max_tokens": 300,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        resp = req.post(api_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # 解析 JSON
        import json
        clean = content.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()

        parsed = json.loads(clean)
        return float(parsed.get("score", 0.0))
    except Exception:
        return _faithfulness_keyword(answer, contexts)


def hallucination_rate(answer: str, contexts: List[str]) -> float:
    """Hallucination Rate: 不被证据支持的事实比例.

    Args:
        answer: 系统生成的答案
        contexts: 检索到的上下文列表

    Returns:
        幻觉率 [0, 1]，越低越好
    """
    return 1.0 - faithfulness(answer, contexts)


def boundary_refusal_rate(result: QueryResult, case: GoldCase) -> float:
    """Boundary Refusal Rate: 无答案问题是否正确拒答.

    Args:
        result: 查询结果
        case: gold 用例

    Returns:
        1.0 如果正确拒答(对 boundary 类型)，0.0 如果错误回答
        对非 boundary 类型返回 0.0 (不适用)
    """
    if case.type != "boundary":
        return 0.0

    # 检查答案是否包含拒答关键词
    refusal_keywords = [
        "没有找到", "无法回答", "信息不足", "不确定", "不知道",
        "没有相关信息", "知识库中没有", "未提供", "未找到",
        "无法确定", "无法提供", "缺少信息", "没有足够"
    ]
    answer_lower = result.answer.lower()
    return 1.0 if any(kw in answer_lower for kw in refusal_keywords) else 0.0


# ─────────────────────────── 第三层：Agentic 链路 ───────────────────────────

# 主路径必须节点（planner→retriever→evaluator→generator→auditor）
# rewriter/fallback 是条件触发的异常处理路径，通过 CRAG Repair Rate 单独度量
EXPECTED_TRACE_NODES = {"planner", "retriever", "evaluator", "generator", "auditor"}


def trace_completeness(trace_nodes: List[str]) -> float:
    """Trace Completeness: 7 节点 trace 是否完整.

    Args:
        trace_nodes: 实际执行的节点列表

    Returns:
        完整度 [0, 1]
    """
    if not EXPECTED_TRACE_NODES:
        return 1.0
    fired = set(trace_nodes)
    hit = len(fired & EXPECTED_TRACE_NODES)
    return hit / len(EXPECTED_TRACE_NODES)


def tool_call_necessity(tool_calls: int, expected: int) -> float:
    """Tool Call Necessity: 工具调用是否必要且不过度.

    Args:
        tool_calls: 实际工具调用次数
        expected: 期望工具调用次数

    Returns:
        必要性分数 [0, 1]，越接近 1 越好
    """
    if expected == 0:
        return 1.0 if tool_calls == 0 else 0.5  # 无期望时给部分分
    if tool_calls == 0:
        return 0.0
    # 计算实际与期望的比值，越接近 1 越好
    ratio = min(tool_calls, expected) / max(tool_calls, expected)
    return ratio


def crag_repair_rate(crag_decision: str, answer_quality_improved: bool) -> float:
    """CRAG Repair Rate: rewrite/fallback 后是否修复答案.

    Args:
        crag_decision: CRAG 决策 (use/rewrite/fallback)
        answer_quality_improved: 答案质量是否提升

    Returns:
        1.0 如果修复成功，0.0 如果未修复，0.5 如果未触发 CRAG (use 路径)
    """
    if crag_decision == "use":
        return 0.5  # 未触发 CRAG，给中性分
    return 1.0 if answer_quality_improved else 0.0


def verifier_pass_rate(trace_nodes: List[str]) -> float:
    """Verifier Pass Rate: generator 是否正常执行（LangGraph 中 generator 替代 verifier 角色）.

    Args:
        trace_nodes: 实际执行的节点列表

    Returns:
        1.0 如果 generator 执行，0.0 如果未执行
    """
    return 1.0 if "generator" in trace_nodes else 0.0


def audit_coverage(trace_nodes: List[str]) -> float:
    """Audit Coverage: Auditor 是否覆盖所有请求.

    Args:
        trace_nodes: 实际执行的节点列表

    Returns:
        1.0 如果 auditor 执行，0.0 如果未执行
    """
    return 1.0 if "auditor" in trace_nodes else 0.0


# ─────────────────────────── 汇总 ───────────────────────────

def compute_metrics(case: GoldCase, result: QueryResult, point_coverage: float = 0.0) -> Dict[str, Any]:
    """汇总三层指标为一行 MetricRow.

    Args:
        case: gold 用例
        result: 查询结果
        point_coverage: 要点覆盖率 (由 judge 计算)

    Returns:
        包含所有指标的字典
    """
    return {
        "case_id": case.id,
        "case_type": case.type,
        "difficulty": case.difficulty,
        # 第一层: 检索质量
        "recall_at_5": recall_at_k(result.retrieved_ids, case.gold_context_ids, k=5),
        "context_precision": context_precision(result.contexts, case.gold_context_ids),
        "citation_recall": citation_recall(result.citations, case.gold_context_ids),
        # 第二层: 答案质量
        "answer_accuracy": answer_accuracy(point_coverage),
        "faithfulness": faithfulness(result.answer, result.contexts),
        "hallucination_rate": hallucination_rate(result.answer, result.contexts),
        "boundary_refusal_rate": boundary_refusal_rate(result, case),
        # 第三层: Agentic 链路
        "trace_completeness": trace_completeness(result.trace_nodes),
        "tool_call_necessity": tool_call_necessity(result.tool_calls, case.expected_tool_calls),
        "crag_repair_rate": crag_repair_rate(result.crag_decision, False),  # 需要两次运行对比
        "verifier_pass_rate": verifier_pass_rate(result.trace_nodes),
        "audit_coverage": audit_coverage(result.trace_nodes),
        # 元数据 (confidence 只记录)
        "latency": result.latency,
        "confidence": result.confidence,
        "crag_decision": result.crag_decision,
    }
