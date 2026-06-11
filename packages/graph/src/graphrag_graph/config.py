"""Configuration for the v3.1 LangGraph orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CragThresholds:
    """CRAG decision thresholds.

    v3.3 values (tuned after 50-question eval):
      * score >= 0.5              → ``use`` (forward to generator)
      * 0.2 <= score < 0.5        → ``rewrite`` (loop back through retriever)
      * score < 0.2               → ``fallback`` (low-confidence response)
    """

    use: float = 0.5
    rewrite_low: float = 0.2

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
    llm_timeout_s: float = 20.0
