"""Operational readiness helpers for the legacy FastAPI backend."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from config.settings import settings


def _safe_stats(name: str, fn) -> dict[str, Any]:
    try:
        stats = fn()
        return {"status": "ok", "details": stats}
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__, "message": str(exc)[:200]}


def dependency_status() -> dict[str, Any]:
    """Return lightweight dependency state without forcing external services up."""
    from app.services.bm25_store import bm25_store
    from app.services.kg_service import kg_service
    from app.services.vector_store import embedding_service, vector_store

    vector = _safe_stats("vector_store", vector_store.get_stats)
    bm25 = _safe_stats("bm25_store", bm25_store.get_stats)
    graph = _safe_stats("graph_store", kg_service.get_stats)
    embedding_mode = "hash_fallback" if getattr(embedding_service, "use_tfidf", False) else "model"

    if graph.get("details", {}).get("status") == "disconnected":
        graph["status"] = "degraded"

    return {
        "vector_store": vector,
        "bm25_store": bm25,
        "graph_store": graph,
        "embedding": {"status": "ok", "mode": embedding_mode},
    }


def observability_status() -> dict[str, Any]:
    return {
        "logging": {
            "status": "ok",
            "level": settings.LOG_LEVEL,
            "dir": settings.LOG_DIR or "backend/data/logs",
        },
        "langfuse": {
            "configured": bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")),
            "host": os.getenv("LANGFUSE_HOST", ""),
        },
    }


def readiness_payload() -> dict[str, Any]:
    dependencies = dependency_status()
    has_error = any(item.get("status") == "error" for item in dependencies.values())
    has_degraded = any(item.get("status") == "degraded" for item in dependencies.values())
    status = "error" if has_error else "degraded" if has_degraded else "ready"
    return {
        "status": status,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(UTC).isoformat(),
        "auth_enabled": settings.ENABLE_AUTH,
        "rate_limit_per_min": settings.RATE_LIMIT_PER_MIN,
        "dependencies": dependencies,
        "observability": observability_status(),
    }
