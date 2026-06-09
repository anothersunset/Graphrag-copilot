"""LLM Judge 模块.

职责: 逐点判定要点覆盖 / faithfulness / 拒答是否正确。
confidence 不参与判定，只落日志。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import requests

from eval.graphrag_client import GoldCase, QueryResult


# LLM API 配置
LLM_API_URL = os.getenv("LLM_API_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions")
LLM_API_KEY = os.getenv("ZHIPU_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "glm-4-flash")


def _call_llm(messages: List[Dict[str, str]], temperature: float = 0.0) -> str:
    """调用 LLM API."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    resp = requests.post(LLM_API_URL, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def judge_case(case: GoldCase, result: QueryResult) -> Dict[str, Any]:
    """LLM judge 逐点判定.

    判定维度:
    1. 要点覆盖: 每个 gold_answer_point 是否在答案中体现
    2. Faithfulness: 答案是否被上下文支持
    3. 拒答判定: boundary 类型是否正确拒答

    Args:
        case: gold 用例
        result: 查询结果

    Returns:
        {
            "point_coverage": float,
            "point_details": [{"point": str, "covered": bool, "reason": str}],
            "faithfulness_judge": float,
            "refusal_correct": bool,
            "judge_raw": str,
        }
    """
    # 构造逐点判定 prompt
    points_text = "\n".join([f"- {p}" for p in case.gold_answer_points])
    contexts_text = "\n\n".join([f"[{i+1}] {c[:500]}" for i, c in enumerate(result.contexts[:5])])

    system_prompt = """你是严谨的答案评判专家。请逐点判定答案是否覆盖了要点。

输出严格 JSON:
{
  "point_details": [
    {"point": "要点文本", "covered": true/false, "reason": "判定理由"}
  ],
  "faithfulness_score": 0.0-1.0,
  "refusal_correct": true/false
}

判定规则:
1. 要点覆盖: 答案中是否包含该要点的核心信息（允许换表述）
2. Faithfulness: 答案中的事实是否都能在上下文中找到依据
3. 拒答判定: 如果是 boundary 类型，答案是否明确表示无法回答"""

    user_prompt = f"""问题: {case.question}

类型: {case.type}
期望要点:
{points_text}

系统答案:
{result.answer}

检索上下文:
{contexts_text}

请判定。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw = _call_llm(messages)
        # 尝试解析 JSON
        # 处理可能的 markdown 代码块
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()

        parsed = json.loads(clean)
    except (json.JSONDecodeError, Exception) as e:
        # 解析失败时返回保守估计
        return {
            "point_coverage": 0.0,
            "point_details": [],
            "faithfulness_judge": 0.0,
            "refusal_correct": False,
            "judge_raw": str(raw) if 'raw' in dir() else str(e),
            "judge_error": str(e),
        }

    # 计算要点覆盖率
    point_details = parsed.get("point_details", [])
    covered = sum(1 for p in point_details if p.get("covered", False))
    total = len(case.gold_answer_points)
    point_coverage = covered / total if total > 0 else 0.0

    # 拒答判定
    refusal_correct = parsed.get("refusal_correct", False)
    if case.type != "boundary":
        refusal_correct = True  # 非 boundary 类型不评判拒答

    return {
        "point_coverage": point_coverage,
        "point_details": point_details,
        "faithfulness_judge": float(parsed.get("faithfulness_score", 0.0)),
        "refusal_correct": refusal_correct,
        "judge_raw": raw if 'raw' in dir() else "",
    }


def human_agreement(judge_rows: List[Dict], human_rows: List[Dict]) -> Dict[str, float]:
    """对约 20% 抽检样本计算 judge 与人工的一致率 + Cohen's kappa.

    Args:
        judge_rows: LLM judge 结果列表，每项需有 case_id 和 point_coverage
        human_rows: 人工标注结果列表，每项需有 case_id 和 point_coverage

    Returns:
        {
            "agreement_rate": float,
            "cohens_kappa": float,
            "n_samples": int,
        }
    """
    if not judge_rows or not human_rows:
        return {"agreement_rate": 0.0, "cohens_kappa": 0.0, "n_samples": 0}

    # 按 case_id 对齐
    judge_map = {r["case_id"]: r for r in judge_rows}
    human_map = {r["case_id"]: r for r in human_rows}
    common_ids = set(judge_map.keys()) & set(human_map.keys())

    if not common_ids:
        return {"agreement_rate": 0.0, "cohens_kappa": 0.0, "n_samples": 0}

    # 二值化: point_coverage >= 0.5 视为 "覆盖"
    agreements = 0
    tp = fp = fn = tn = 0
    for cid in common_ids:
        j_covered = judge_map[cid].get("point_coverage", 0.0) >= 0.5
        h_covered = human_map[cid].get("point_coverage", 0.0) >= 0.5
        if j_covered == h_covered:
            agreements += 1
        if j_covered and h_covered:
            tp += 1
        elif j_covered and not h_covered:
            fp += 1
        elif not j_covered and h_covered:
            fn += 1
        else:
            tn += 1

    n = len(common_ids)
    agreement_rate = agreements / n

    # Cohen's kappa
    p_o = agreement_rate  # observed agreement
    p_e = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n) if n > 0 else 0
    kappa = (p_o - p_e) / (1 - p_e) if (1 - p_e) > 0 else 0.0

    return {
        "agreement_rate": round(agreement_rate, 4),
        "cohens_kappa": round(kappa, 4),
        "n_samples": n,
    }
