"""Small adapters shared by the FastAPI endpoints."""

from __future__ import annotations

from typing import Any


def ask_payload(req: Any) -> dict[str, Any]:
    """Map an AskRequest onto the orchestrator's input state keys."""
    return {"question": req.query, "top_k": req.top_k}
