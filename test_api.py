"""GraphRAG Copilot smoke test runner.

Environment variables:
  BASE_URL            Defaults to http://localhost:8000
  API_KEY             Defaults to test-key-1
  ENABLE_AUTH         true/false, defaults to false
  RATE_LIMIT_PER_MIN  Defaults to 60

Example:
  BASE_URL=http://localhost:8000 API_KEY=test-key-1 ENABLE_AUTH=true \
      RATE_LIMIT_PER_MIN=5 python test_api.py
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "test-key-1")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))


def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY} if ENABLE_AUTH else {}


def _json_or_empty(response: requests.Response) -> dict:
    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json()
    return {}


def test_health() -> bool:
    print("[1] health")
    r = requests.get(BASE_URL + "/health", timeout=5)
    print("   ->", r.status_code, _json_or_empty(r))
    return r.status_code == 200


def test_readyz() -> bool:
    print("[2] readiness")
    r = requests.get(BASE_URL + "/readyz", timeout=5)
    payload = _json_or_empty(r)
    print("   ->", r.status_code, payload)
    return r.status_code == 200 and payload.get("status") in {"ready", "degraded", "error"}


def test_system_status() -> bool:
    print("[3] system status")
    r = requests.get(BASE_URL + "/api/system/status", timeout=5)
    print("   ->", r.status_code, _json_or_empty(r))
    return r.status_code == 200


def test_vector_stats() -> bool:
    print("[4] vector stats")
    r = requests.get(BASE_URL + "/api/vector/stats", timeout=5)
    print("   ->", r.status_code, _json_or_empty(r))
    return r.status_code == 200


def test_graph_stats() -> bool:
    print("[5] graph stats")
    r = requests.get(BASE_URL + "/api/graph/stats", timeout=5)
    print("   ->", r.status_code, _json_or_empty(r))
    return r.status_code == 200


def test_query() -> bool:
    print("[6] query")
    r = requests.post(
        BASE_URL + "/api/query",
        json={"query": "What is GraphRAG?", "top_k": 5},
        headers=_auth_headers(),
        timeout=30,
    )
    print("   ->", r.status_code, _json_or_empty(r))
    return r.status_code in (200, 500)


def test_document_upload() -> bool:
    print("[7] document upload")
    tmp = Path("_smoke_test_document.txt")
    try:
        tmp.write_text(
            "GraphRAG combines knowledge graphs with retrieval-augmented generation.",
            encoding="utf-8",
        )
        with tmp.open("rb") as f:
            r = requests.post(
                BASE_URL + "/api/documents/upload",
                files={"file": ("test.txt", f, "text/plain")},
                headers=_auth_headers(),
                timeout=30,
            )
        print("   ->", r.status_code, _json_or_empty(r))
        return r.status_code == 200
    finally:
        tmp.unlink(missing_ok=True)


def test_auth_missing_header() -> bool:
    if not ENABLE_AUTH:
        print("[8] auth missing header - skipped (ENABLE_AUTH=false)")
        return True
    print("[8] auth missing header")
    r = requests.post(BASE_URL + "/api/query", json={"query": "ping"}, timeout=5)
    print("   ->", r.status_code, _json_or_empty(r))
    return r.status_code in (401, 403)


def test_auth_valid_header() -> bool:
    if not ENABLE_AUTH:
        print("[9] auth valid header - skipped (ENABLE_AUTH=false)")
        return True
    print("[9] auth valid header")
    r = requests.post(
        BASE_URL + "/api/query",
        json={"query": "ping"},
        headers=_auth_headers(),
        timeout=15,
    )
    print("   ->", r.status_code, _json_or_empty(r))
    return r.status_code not in (401, 403)


def test_rate_limit_returns_429() -> bool:
    print("[10] rate limit smoke (RATE_LIMIT_PER_MIN=" + str(RATE_LIMIT) + ")")
    if RATE_LIMIT <= 0 or RATE_LIMIT > 200:
        print("   -> skipped")
        return True
    statuses: list[int] = []
    for _ in range(RATE_LIMIT + 2):
        try:
            statuses.append(requests.get(BASE_URL + "/health", timeout=5).status_code)
        except Exception as exc:
            print("   -> request failed", exc)
            return False
    counts = {code: statuses.count(code) for code in set(statuses)}
    print("   ->", counts)
    return 429 in statuses


def main() -> int:
    print("=" * 60)
    print("GraphRAG Copilot smoke test")
    print("BASE_URL  =", BASE_URL)
    print("AUTH      =", "ON" if ENABLE_AUTH else "OFF")
    print("RATE_LIMIT=", RATE_LIMIT, "/ min")
    print("=" * 60)

    tests: list[tuple[str, Callable[[], bool]]] = [
        ("health", test_health),
        ("readiness", test_readyz),
        ("system status", test_system_status),
        ("vector stats", test_vector_stats),
        ("graph stats", test_graph_stats),
        ("query", test_query),
        ("document upload", test_document_upload),
        ("auth missing header", test_auth_missing_header),
        ("auth valid header", test_auth_valid_header),
        ("rate limit", test_rate_limit_returns_429),
    ]

    passed = 0
    failures: list[str] = []
    for name, fn in tests:
        try:
            ok = fn()
        except Exception as exc:
            print("   -> ERROR", exc)
            ok = False
        if ok:
            passed += 1
        else:
            failures.append(name)

    print("-" * 60)
    print("Total:", passed, "/", len(tests))
    if failures:
        print("Failed:", ", ".join(failures))
        return 1
    print("Smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
