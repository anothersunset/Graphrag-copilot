"""AuditRecord — every node decision in LangGraph emits one of these.

Invariant: ``审计覆盖率 = 1.00`` — every state transition logged.
The Auditor node (W7) consumes these to compute Tool Call Necessity.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AuditOutcome(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class AuditRecord(BaseModel):
    """One LangGraph node transition + outcome."""

    model_config = ConfigDict(frozen=True)

    record_id: UUID = Field(default_factory=uuid4)
    parent_trace_id: UUID
    node_name: str
    occurred_at: datetime
    outcome: AuditOutcome
    duration_ms: float = Field(ge=0)
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
