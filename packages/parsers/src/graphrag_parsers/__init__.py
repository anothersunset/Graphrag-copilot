"""Document parsing + chunking for GraphRAG Copilot v3.1."""
from .chunker import ChunkRecord, SemanticChunker
from .late_chunking import LateChunkingPlanner, LateChunkSpan
from .markdown import MarkdownSplitter

__version__ = "0.1.0"

__all__ = [
    "ChunkRecord",
    "LateChunkSpan",
    "LateChunkingPlanner",
    "MarkdownSplitter",
    "SemanticChunker",
    "__version__",
]
