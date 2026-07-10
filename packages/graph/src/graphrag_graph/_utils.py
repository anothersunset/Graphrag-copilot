"""Internal helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from .state import RetrievalHit


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def digest(obj: Any, *, n: int = 12) -> str:
    payload = json.dumps(obj, default=str, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:n]


def merge_hits(hits: list[RetrievalHit], *, dedup_key: str = "chunk_id") -> list[RetrievalHit]:
    """Stable dedup of hits by key, preserving the highest score per chunk."""
    by_key: dict[str, RetrievalHit] = {}
    for h in hits:
        k = h.get(dedup_key) or h.get("content", "")[:80]
        if k not in by_key:
            by_key[k] = h.copy()
        else:
            existing = by_key[k]
            if h.get("score", 0.0) > existing.get("score", 0.0):
                by_key[k] = h.copy()
    return list(by_key.values())
