"""GraphRAG Copilot - JSON 容错工具"""
from __future__ import annotations

import json
import re
from typing import Any, Dict

def extract_json_object(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    candidates = []

    if "```json" in text:
        candidates.append(text.split("```json", 1)[1].split("```", 1)[0])

    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            candidates.append(parts[1])

    candidates.append(text)

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.append(match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate.strip())
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue

    return {"raw_response": text}
