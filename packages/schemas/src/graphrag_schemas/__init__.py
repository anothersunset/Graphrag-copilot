"""Shared pydantic schemas for GraphRAG Copilot."""

from .evidence import (
    ChunkEvidence,
    EvidencePack,
    GraphNode,
    GraphPath,
    GraphRel,
    RerankTraceRow,
)
from .retrieval_trace import (
    CRAGBranch,
    CRAGDecision,
    RetrievalStep,
    RetrievalTrace,
    RetrieverKind,
    ToolKind,
    ToolSpec,
)

__version__ = "0.1.0"

__all__ = [
    "CRAGBranch",
    "CRAGDecision",
    "ChunkEvidence",
    "EvidencePack",
    "GraphNode",
    "GraphPath",
    "GraphRel",
    "RerankTraceRow",
    "RetrievalStep",
    "RetrievalTrace",
    "RetrieverKind",
    "ToolKind",
    "ToolSpec",
    "__version__",
]
