"""Configuration for the v3.1 LangGraph orchestrator."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CragThresholds:
    """CRAG decision thresholds.

    Locked v3.1 values:
      * score >= 0.7              → ``use`` (forward to generator)
      * 0.3 <= score < 0.7        → ``rewrite`` (loop back through retriever)
      * score < 0.3               → ``fallback`` (low-confidence response)
    """

    use: float = 0.7
    rewrite_low: float = 0.3

    def decide(self, score: float) -> str:
        if score >= self.use:
            return "use"
        if score >= self.rewrite_low:
            return "rewrite"
        return "fallback"


@dataclass(frozen=True)
class GraphConfig:
    """Top-level orchestrator config."""

    crag: CragThresholds = field(default_factory=CragThresholds)
    max_rewrites: int = 2  # CRAG rewrite cap (locked v3.1 value)
    max_hits: int = 20
    top_k_after_rerank: int = 5
    enable_kg: bool = True
    enable_web_search: bool = False
    auditor_strict: bool = False

    # LLM
    planner_model: str = "openai/gpt-4o-mini"
    generator_model: str = "openai/gpt-4o-mini"
    auditor_model: str = "openai/gpt-4o-mini"
    llm_timeout_s: float = 30.0
