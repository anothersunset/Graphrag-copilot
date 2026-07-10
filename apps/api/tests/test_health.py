"""Health and readiness contracts for the canonical application."""

from fastapi.testclient import TestClient
from graphrag_api import __version__
from graphrag_api.app import create_app


def test_healthz_is_public_and_ready_fails_closed_without_index() -> None:
    with TestClient(create_app()) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["version"] == __version__

        ready = client.get("/readyz")
        assert ready.status_code == 503
        assert ready.json()["status"] == "not_ready"


def test_openapi_exposes_canonical_business_routes() -> None:
    with TestClient(create_app()) as client:
        spec = client.get("/openapi.json").json()
    assert "/healthz" in spec["paths"]
    assert "/readyz" in spec["paths"]
    assert "/v1/ask" in spec["paths"]
    assert "/v1/ask/stream" in spec["paths"]
    assert "/v1/runs/{run_id}" in spec["paths"]


def test_mcp_is_mounted_once() -> None:
    app = create_app()
    assert [getattr(route, "name", None) for route in app.routes].count("mcp") == 1
