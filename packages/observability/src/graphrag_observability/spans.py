"""Node-aware span helpers and AuditEntry export."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


@contextmanager
def NodeSpan(
    trace: Any, *, name: str, input: Any = None, metadata: dict | None = None
) -> Iterator[Any]:
    """Context manager that opens a Langfuse span scoped to one graph node."""
    span = trace.span(name=name, input=input, metadata=metadata or {})
    try:
        yield span
    finally:
        try:
            span.end()
        except Exception:  # pragma: no cover - defensive
            pass


class AuditExporter:
    """Export ``graphrag_graph.AuditEntry`` rows as Langfuse events.

    Decoupled from graphrag_graph at import time so observability has no
    hard dependency on the graph package (helps test isolation).
    """

    def __init__(self, trace: Any) -> None:
        self._trace = trace

    def export(self, entry: Any) -> None:
        node = getattr(entry, "node", None) or (
            entry.get("node") if isinstance(entry, dict) else None
        )
        timestamp = getattr(entry, "timestamp", None) or (
            entry.get("timestamp") if isinstance(entry, dict) else None
        )
        summary = getattr(entry, "summary", None) or (
            entry.get("summary") if isinstance(entry, dict) else None
        )
        detail = (
            getattr(entry, "detail", None)
            or (entry.get("detail") if isinstance(entry, dict) else None)
            or {}
        )

        try:
            self._trace.event(
                name=f"audit.{node or 'unknown'}",
                input={"summary": summary, "timestamp": timestamp},
                metadata=detail,
            )
        except Exception:  # pragma: no cover - defensive
            pass

    def export_all(self, entries: list) -> None:
        for entry in entries:
            self.export(entry)
