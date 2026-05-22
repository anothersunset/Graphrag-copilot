"""GraphRAG Copilot v3.1 — LangGraph 7-node Agentic RAG orchestrator."""

from .config import CragThresholds, GraphConfig
from .contracts import (
    AuditorClient,
    CragScorer,
    LLMClient,
    QueryRewriter,
    Reranker,
    Retriever,
)
from .graph import build_graph
from .state import (
    AuditEntry,
    Citation,
    GraphState,
    RetrievalHit,
    ToolCall,
    initial_state,
)

__version__ = "0.1.0"

__all__ = [
    "AuditEntry",
    "AuditorClient",
    "Citation",
    "CragScorer",
    "CragThresholds",
    "GraphConfig",
    "GraphState",
    "LLMClient",
    "QueryRewriter",
    "Reranker",
    "RetrievalHit",
    "Retriever",
    "ToolCall",
    "__version__",
    "build_graph",
    "initial_state",
]
