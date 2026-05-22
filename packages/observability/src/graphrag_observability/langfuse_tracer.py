"""Langfuse 2.x tracer wrapper with no-op fallback."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator, Protocol

logger = logging.getLogger(__name__)


class Tracer(Protocol):
    def trace(self, name: str, *, input: Any = None, metadata: dict | None = None) -> "TraceHandle": ...
    def flush(self) -> None: ...


class TraceHandle(Protocol):
    def span(self, name: str, *, input: Any = None, metadata: dict | None = None) -> "SpanHandle": ...
    def event(self, name: str, *, input: Any = None, metadata: dict | None = None) -> None: ...
    def update(self, *, output: Any = None, metadata: dict | None = None) -> None: ...
    def end(self, *, output: Any = None) -> None: ...


class SpanHandle(Protocol):
    def update(self, *, output: Any = None, metadata: dict | None = None) -> None: ...
    def end(self, *, output: Any = None) -> None: ...


class NoopSpan:
    def update(self, *, output: Any = None, metadata: dict | None = None) -> None: ...
    def end(self, *, output: Any = None) -> None: ...


class NoopTrace:
    def span(self, name: str, *, input: Any = None, metadata: dict | None = None) -> NoopSpan:
        return NoopSpan()

    def event(self, name: str, *, input: Any = None, metadata: dict | None = None) -> None: ...
    def update(self, *, output: Any = None, metadata: dict | None = None) -> None: ...
    def end(self, *, output: Any = None) -> None: ...


class NoopTracer:
    """Tracer that does nothing. Used when Langfuse is not configured."""

    def trace(self, name: str, *, input: Any = None, metadata: dict | None = None) -> NoopTrace:
        return NoopTrace()

    def flush(self) -> None: ...


class LangfuseTracer:
    """Thin wrapper around the official Langfuse 2.x SDK."""

    def __init__(self, *, client: Any | None = None) -> None:
        if client is not None:
            self._client = client
            return
        try:
            from langfuse import Langfuse
        except ImportError as e:
            raise RuntimeError(
                "LangfuseTracer requires the langfuse SDK (^2.50). "
                "Install with 'graphrag-observability'."
            ) from e
        self._client = Langfuse(
            public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
            host=os.environ.get("LANGFUSE_HOST"),
        )

    def trace(self, name: str, *, input: Any = None, metadata: dict | None = None) -> Any:
        try:
            return self._client.trace(name=name, input=input, metadata=metadata or {})
        except Exception:
            logger.exception("langfuse trace open failed; falling back to noop")
            return NoopTrace()

    def flush(self) -> None:
        try:
            self._client.flush()
        except Exception:
            logger.exception("langfuse flush failed")


_default_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    """Process-wide tracer; LangfuseTracer if configured else NoopTracer."""
    global _default_tracer
    if _default_tracer is not None:
        return _default_tracer
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        try:
            _default_tracer = LangfuseTracer()
            return _default_tracer
        except Exception:
            logger.exception("failed to build LangfuseTracer; using noop")
    _default_tracer = NoopTracer()
    return _default_tracer


@contextmanager
def use_tracer(tracer: Tracer) -> Iterator[Tracer]:
    """Override the global tracer for the duration of a `with` block."""
    global _default_tracer
    prev = _default_tracer
    _default_tracer = tracer
    try:
        yield tracer
    finally:
        _default_tracer = prev
