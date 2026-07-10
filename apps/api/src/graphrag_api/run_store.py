"""Small bounded run store used by the demo API.

The store is deliberately process-local. It gives the web UI stable run URLs
without pretending to be durable persistence.
"""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any


@dataclass
class _StoredRun:
    value: dict[str, Any]
    expires_at: float


class RunStore:
    def __init__(self, *, capacity: int = 100, ttl_seconds: int = 3600) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")
        self._capacity = capacity
        self._ttl_seconds = ttl_seconds
        self._items: OrderedDict[str, _StoredRun] = OrderedDict()
        self._lock = Lock()

    def put(self, run_id: str, value: dict[str, Any]) -> None:
        now = monotonic()
        with self._lock:
            self._purge(now)
            self._items.pop(run_id, None)
            self._items[run_id] = _StoredRun(deepcopy(value), now + self._ttl_seconds)
            while len(self._items) > self._capacity:
                self._items.popitem(last=False)

    def get(self, run_id: str) -> dict[str, Any] | None:
        now = monotonic()
        with self._lock:
            self._purge(now)
            item = self._items.get(run_id)
            if item is None:
                return None
            self._items.move_to_end(run_id)
            return deepcopy(item.value)

    def _purge(self, now: float) -> None:
        expired = [key for key, item in self._items.items() if item.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)
