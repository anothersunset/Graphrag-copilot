"""Uvicorn entrypoint for the canonical API application."""

from .app import app, create_app

__all__ = ["app", "create_app"]
