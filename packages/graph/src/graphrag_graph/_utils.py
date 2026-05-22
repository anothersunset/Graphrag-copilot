"""Internal helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def digest(obj: Any, *, n: int = 12) -> str:
    payload = json.dumps(obj, default=str, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:n]


def merge_hits(hits: list, *, dedup_key: str = "chunk_id") -> list:
    """Stable dedup of hits by key, preserving the highest score per chunk."""
    by_key: dict[str, dict] = {}
    for h in hits:
        k = h.get(dedup_key) or h.get("content", "")[:80]
        if k not in by_key:
            by_key[k] = dict(h)
        else:
            existing = by_key[k]
            if h.get("score", 0.0) > existing.get("score", 0.0):
                by_key[k] = dict(h)
    return list(by_key.values())
