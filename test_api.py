"""Smoke-test the canonical ``apps/api`` GraphRAG service.

Run the API first with ``make api``, then execute ``make smoke``.
Override ``BASE_URL`` and ``GRAPHRAG_API_KEY`` when needed.
"""

from __future__ import annotations

import os

import httpx

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("GRAPHRAG_API_KEY")
TIMEOUT = float(os.getenv("SMOKE_TIMEOUT_SECONDS", "30"))


def _headers() -> dict[str, str]:
    return {"x-api-key": API_KEY} if API_KEY else {}


def _check(name: str, condition: bool, detail: str = "") -> bool:
    marker = "PASS" if condition else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{marker}] {name}{suffix}")
    return condition


def main() -> int:
    failures = 0
    with httpx.Client(base_url=BASE_URL, headers=_headers(), timeout=TIMEOUT) as client:
        health = client.get("/healthz")
        failures += not _check("GET /healthz", health.status_code == 200, str(health.status_code))

        ready = client.get("/readyz")
        failures += not _check("GET /readyz", ready.status_code == 200, str(ready.status_code))

        ask = client.post("/v1/ask", json={"query": "What is GraphRAG?", "top_k": 3})
        ask_ok = ask.status_code == 200
        payload = ask.json() if ask_ok else {}
        required = {
            "run_id",
            "answer",
            "verdict",
            "cited_chunk_ids",
            "audit",
            "retrieval_trace",
        }
        contract_ok = ask_ok and required.issubset(payload)
        failures += not _check("POST /v1/ask contract", contract_ok, str(ask.status_code))

        run_id = payload.get("run_id")
        if run_id:
            stored = client.get(f"/v1/runs/{run_id}")
            failures += not _check(
                "GET /v1/runs/{run_id}",
                stored.status_code == 200 and stored.json().get("run_id") == run_id,
                str(stored.status_code),
            )

    print(f"Smoke result: {'passed' if failures == 0 else f'{failures} failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
