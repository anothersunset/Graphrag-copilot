"""数据集加载模块.

职责: 读取 seed_benchmark.jsonl，逐行解析为 GoldCase，做字段校验。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from eval.graphrag_client import GoldCase


def load_benchmark(path: str) -> List[GoldCase]:
    """读取 seed_benchmark.jsonl，逐行解析为 GoldCase。

    Args:
        path: jsonl 文件路径

    Returns:
        GoldCase 列表

    Raises:
        ValueError: 字段缺失或类型错误
    """
    cases: List[GoldCase] = []
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Benchmark file not found: {path}")

    with open(p, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Line {lineno}: invalid JSON: {e}") from e

            # 必填字段校验
            required = ["id", "type", "difficulty", "question", "gold_answer",
                         "gold_answer_points", "gold_context_ids"]
            missing = [k for k in required if k not in row]
            if missing:
                raise ValueError(f"Line {lineno}: missing fields: {missing}")

            # 类型校验
            if row["type"] not in ("factual", "relational", "multihop", "crossdoc", "boundary"):
                raise ValueError(f"Line {lineno}: invalid type: {row['type']}")
            if row["difficulty"] not in ("easy", "medium", "hard"):
                raise ValueError(f"Line {lineno}: invalid difficulty: {row['difficulty']}")

            cases.append(GoldCase(
                id=row["id"],
                type=row["type"],
                difficulty=row["difficulty"],
                question=row["question"],
                gold_answer=row["gold_answer"],
                gold_answer_points=row["gold_answer_points"],
                gold_context_ids=row["gold_context_ids"],
                supporting_entities=row.get("supporting_entities", []),
                expected_tool_calls=row.get("expected_tool_calls", 0),
                expect_answerable=row.get("expect_answerable", True),
            ))

    return cases
