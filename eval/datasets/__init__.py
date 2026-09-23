"""数据集加载模块.

职责: 读取 seed_benchmark.jsonl，逐行解析为 GoldCase，做字段校验。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from eval.graphrag_client import GoldCase

_GOLD_MAP_FILE = Path(__file__).parent / "gold_context_map.json"


@lru_cache(maxsize=1)
def load_gold_context_map() -> Dict[str, List[str]]:
    """Load the semantic-ID -> real chunk-ID map (see gold_context_map.json).

    Returns an empty dict when the map file is absent, so metric code can
    treat mapping as best-effort; dataset validation is separate and loud.
    """
    if not _GOLD_MAP_FILE.exists():
        return {}
    with open(_GOLD_MAP_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {k: list(v) for k, v in raw.items() if not k.startswith("_")}


def expand_gold_context_ids(gold_context_ids: List[str]) -> List[str]:
    """Expand semantic gold ids into real chunk ids via the gold map.

    Unmapped ids pass through unchanged so the metric still sees (and can
    report) an honest zero rather than silently dropping gold.
    """
    mapping = load_gold_context_map()
    expanded: List[str] = []
    for gid in gold_context_ids:
        if gid in mapping:
            expanded.extend(mapping[gid])
        else:
            expanded.append(gid)
    return expanded


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
