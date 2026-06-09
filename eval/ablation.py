"""A~E 消融实验配置与批量运行.

消融组:
  A · Vector only        → 仅 Qdrant dense vector，普通向量 RAG 下限
  B · +BM25              → dense + sparse 混合，专名/模块名召回提升
  C · +Graph             → 加 Neo4j 邻居/路径，多跳/实体关系增益
  D · +Contextual+CRAG   → contextual chunk + rewrite/fallback，降幻觉
  E · Full Agentic       → 7 节点 + Verifier + Auditor，可追溯/可审计/边界拒答
"""
from __future__ import annotations

from typing import Any, Dict, List

from eval.graphrag_client import GoldCase, QueryResult, run_query
from eval.metrics import compute_metrics
from eval.judge import judge_case


# ─────────────────────────── 消融配置 ───────────────────────────

ABLATION_GROUPS: Dict[str, Dict[str, Any]] = {
    "A": {
        "name": "Vector only",
        "vector": True,
        "bm25": False,
        "graph": False,
        "contextual": False,
        "crag": False,
        "verifier": False,
        "auditor": False,
    },
    "B": {
        "name": "Vector + BM25",
        "vector": True,
        "bm25": True,
        "graph": False,
        "contextual": False,
        "crag": False,
        "verifier": False,
        "auditor": False,
    },
    "C": {
        "name": "+ Graph Retrieval",
        "vector": True,
        "bm25": True,
        "graph": True,
        "contextual": False,
        "crag": False,
        "verifier": False,
        "auditor": False,
    },
    "D": {
        "name": "+ Contextual + CRAG",
        "vector": True,
        "bm25": True,
        "graph": True,
        "contextual": True,
        "crag": True,
        "verifier": False,
        "auditor": False,
    },
    "E": {
        "name": "Full Agentic GraphRAG",
        "vector": True,
        "bm25": True,
        "graph": True,
        "contextual": True,
        "crag": True,
        "verifier": True,
        "auditor": True,
    },
}


def run_single_group(
    group_name: str,
    cases: List[GoldCase],
    base_url: str | None = None,
) -> Dict[str, Any]:
    """运行单个消融组.

    Args:
        group_name: 组名 (A~E)
        cases: gold 用例列表
        base_url: API 地址

    Returns:
        {
            "group": str,
            "config": dict,
            "metrics": list[dict],
            "aggregated": dict,
        }
    """
    if group_name not in ABLATION_GROUPS:
        raise ValueError(f"Unknown group: {group_name}. Valid: {list(ABLATION_GROUPS.keys())}")

    config = ABLATION_GROUPS[group_name].copy()
    metrics_list = []

    for case in cases:
        try:
            kwargs = {"question": case.question, "config": config}
            if base_url:
                kwargs["base_url"] = base_url
            result = run_query(**kwargs)

            # LLM judge 逐点判定
            judge_result = judge_case(case, result)

            # 计算指标
            metrics = compute_metrics(case, result, point_coverage=judge_result["point_coverage"])
            metrics["judge"] = judge_result
            metrics_list.append(metrics)

        except Exception as e:
            metrics_list.append({
                "case_id": case.id,
                "error": str(e),
            })

    # 聚合指标
    valid_metrics = [m for m in metrics_list if "error" not in m]
    aggregated = _aggregate_metrics(valid_metrics) if valid_metrics else {}

    return {
        "group": group_name,
        "config": config,
        "metrics": metrics_list,
        "aggregated": aggregated,
    }


def _aggregate_metrics(metrics_list: List[Dict[str, Any]]) -> Dict[str, float]:
    """聚合指标列表为平均值."""
    if not metrics_list:
        return {}

    # 需要聚合的指标字段
    metric_keys = [
        "recall_at_5", "context_precision", "citation_recall",
        "answer_accuracy", "faithfulness", "hallucination_rate", "boundary_refusal_rate",
        "trace_completeness", "tool_call_necessity", "crag_repair_rate",
        "verifier_pass_rate", "audit_coverage",
        "latency",
    ]

    aggregated = {}
    for key in metric_keys:
        values = [m[key] for m in metrics_list if key in m and m[key] is not None]
        if values:
            aggregated[key] = round(sum(values) / len(values), 4)

    aggregated["n_cases"] = len(metrics_list)
    return aggregated


def run_ablation(
    groups: List[str],
    cases: List[GoldCase],
    base_url: str | None = None,
) -> Dict[str, Any]:
    """逐组以对应 config 跑 benchmark，汇总各组指标.

    Args:
        groups: 要运行的组名列表 (A~E)
        cases: gold 用例列表
        base_url: API 地址

    Returns:
        {
            "groups": {group_name: group_result},
            "summary": {group_name: aggregated_metrics},
        }
    """
    results = {}
    for group_name in groups:
        results[group_name] = run_single_group(group_name, cases, base_url)

    # 提取 summary
    summary = {}
    for gname, gresult in results.items():
        summary[gname] = gresult.get("aggregated", {})

    return {
        "groups": results,
        "summary": summary,
    }
