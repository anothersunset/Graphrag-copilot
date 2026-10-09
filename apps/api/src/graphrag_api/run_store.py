"""Bounded run stores backing ``GET /v1/runs/{run_id}``.

Two interchangeable backends:

* :class:`RunStore` — process-local LRU + TTL (default; zero deps).
* :class:`SqliteRunStore` — same semantics on a SQLite file, so runs
  survive restarts and are visible across uvicorn workers.

Pick via ``GRAPHRAG_RUN_STORE_URL``: unset/``memory://`` → in-memory,
``sqlite:///path/to/runs.db`` → SQLite.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
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


class SqliteRunStore:
    """Capacity + TTL bounded store persisted to a SQLite file.

    Same observable contract as :class:`RunStore`: ``get`` returns a deep
    copy, expired rows read as missing, ``put`` enforces capacity by
    evicting the least-recently-read rows. Safe for multiple threads and
    processes (WAL mode); the lock only serializes this process's
    connections — cross-process safety comes from SQLite itself.
    """

    def __init__(self, path: str | Path, *, capacity: int = 100, ttl_seconds: int = 3600) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")
        self._capacity = capacity
        self._ttl_seconds = ttl_seconds
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(str(target), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id     TEXT PRIMARY KEY,
                payload    TEXT NOT NULL,
                expires_at REAL NOT NULL,
                last_read  REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def put(self, run_id: str, value: dict[str, Any]) -> None:
        now = time.time()
        with self._lock:
            self._conn.execute("DELETE FROM runs WHERE expires_at <= ?", (now,))
            self._conn.execute(
                "INSERT OR REPLACE INTO runs (run_id, payload, expires_at, last_read) "
                "VALUES (?, ?, ?, ?)",
                (run_id, json.dumps(deepcopy(value)), now + self._ttl_seconds, now),
            )
            overflow = self._conn.execute(
                "SELECT COUNT(*) FROM runs"
            ).fetchone()[0] - self._capacity
            if overflow > 0:
                self._conn.execute(
                    "DELETE FROM runs WHERE run_id IN ("
                    "  SELECT run_id FROM runs ORDER BY last_read ASC LIMIT ?"
                    ")",
                    (overflow,),
                )
            self._conn.commit()

    def get(self, run_id: str) -> dict[str, Any] | None:
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM runs WHERE run_id = ? AND expires_at > ?",
                (run_id, now),
            ).fetchone()
            if row is None:
                return None
            self._conn.execute(
                "UPDATE runs SET last_read = ? WHERE run_id = ?", (now, run_id)
            )
            self._conn.commit()
            return json.loads(row[0])

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def build_run_store(url: str | None, *, capacity: int, ttl_seconds: int) -> RunStore | SqliteRunStore:
    """Resolve the configured run-store backend."""
    if not url or url == "memory://":
        return RunStore(capacity=capacity, ttl_seconds=ttl_seconds)
    if url.startswith("sqlite:///"):
        return SqliteRunStore(url[len("sqlite:///"):], capacity=capacity, ttl_seconds=ttl_seconds)
    raise ValueError(
        f"unsupported GRAPHRAG_RUN_STORE_URL {url!r} (use memory:// or sqlite:///path)"
    )
