"""GraphRAG Copilot - JSON 容错工具"""
from __future__ import annotations

import json
import re
from typing import Any, Dict


def _extract_balanced_json(text: str) -> str | None:
    """用括号深度匹配提取第一个完整的 {...} JSON 块."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json_object(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    candidates = []

    # 1. 从 ```json ... ``` 代码块中提取
    if "```json" in text:
        candidates.append(text.split("```json", 1)[1].split("```", 1)[0])

    # 2. 从 ``` ... ``` 代码块中提取
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            candidates.append(parts[1])

    # 3. 用括号深度匹配提取第一个完整 JSON 对象（比贪婪正则更可靠）
    balanced = _extract_balanced_json(text)
    if balanced:
        candidates.append(balanced)

    # 4. 兜底：贪婪正则（处理极端情况）
    match = re.search(r"\{[\s\S]*\}", text)
    if match and match.group(0) not in candidates:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate.strip())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue

    return {"raw_response": text}
