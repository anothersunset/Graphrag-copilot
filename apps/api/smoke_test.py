"""Smoke test for the v3.1 API surface.

Usage:
  BASE_URL=http://localhost:8000 python test_api.py
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = int(os.getenv("TIMEOUT", "10"))


def _ok(name: str, condition: bool) -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")
    return condition


def check_healthz() -> bool:
    r = requests.get(f"{BASE_URL}/healthz", timeout=TIMEOUT)
    return _ok("GET /healthz == 200", r.status_code == 200)


def check_readyz() -> bool:
    r = requests.get(f"{BASE_URL}/readyz", timeout=TIMEOUT)
    return _ok("GET /readyz == 200", r.status_code == 200)


def check_ask_contract() -> bool:
    payload = {"query": "GraphRAG是什么？", "top_k": 3}
    r = requests.post(f"{BASE_URL}/v1/ask", json=payload, timeout=max(TIMEOUT, 30))
    if r.status_code != 200:
        return _ok("POST /v1/ask == 200", False)
    data = r.json()
    required = ["answer", "verdict", "cited_chunk_ids", "audit", "retrieval_trace"]
    return _ok("POST /v1/ask response contract", all(k in data for k in required))


def main() -> int:
    print("=" * 60)
    print("GraphRAG Copilot API smoke test")
    print(f"BASE_URL={BASE_URL}")
    print("=" * 60)

    checks: list[Callable[[], bool]] = [
        check_healthz,
        check_readyz,
        check_ask_contract,
    ]

    failures = 0
    for fn in checks:
        try:
            if not fn():
                failures += 1
        except Exception as exc:
            failures += 1
            print(f"[FAIL] {fn.__name__}: {exc}")

    print("-" * 60)
    print(f"Result: {len(checks) - failures}/{len(checks)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
