"""FastAPI app entrypoint.

Starting in W2 this file wires up the LangGraph orchestrator. For W1 it only
exposes health and readiness probes so CI + Docker can validate the service
shell end-to-end.
"""

from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

from graphrag_api import __version__
from graphrag_api.config import settings

app = FastAPI(
    title="GraphRAG Copilot API",
    version=__version__,
    description="Agentic GraphRAG service with full retrieval traces.",
)


class HealthResponse(BaseModel):
    status: str
    version: str
    env: str
    timestamp: str


@app.get("/healthz", response_model=HealthResponse, tags=["health"])
async def healthz() -> HealthResponse:
    """Liveness probe: always 200 if the process is up."""
    return HealthResponse(
        status="ok",
        version=__version__,
        env=settings.env,
        timestamp=datetime.now(UTC).isoformat(),
    )


@app.get("/readyz", response_model=HealthResponse, tags=["health"])
async def readyz() -> HealthResponse:
    """Readiness probe. W3+: extends to check Qdrant/Neo4j connectivity."""
    return HealthResponse(
        status="ready",
        version=__version__,
        env=settings.env,
        timestamp=datetime.now(UTC).isoformat(),
    )
