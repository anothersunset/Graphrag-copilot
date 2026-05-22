"""Tests for health endpoints."""

from fastapi.testclient import TestClient
from graphrag_api import __version__
from graphrag_api.main import app

client = TestClient(app)


def test_healthz_returns_ok() -> None:
    """Liveness endpoint returns 200 + status=ok."""
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
    assert "timestamp" in body


def test_readyz_returns_ready() -> None:
    """Readiness endpoint returns 200 + status=ready."""
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_openapi_includes_health_routes() -> None:
    """Auto-generated OpenAPI must include both health endpoints."""
    spec = client.get("/openapi.json").json()
    assert "/healthz" in spec["paths"]
    assert "/readyz" in spec["paths"]
