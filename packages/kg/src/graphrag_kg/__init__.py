"""graphrag-kg — GraphRAG index layer.

Pipeline: chunk → extraction (LLM + gleaning, or co-occurrence fallback)
→ entity resolution → KnowledgeGraphIndex (networkx) → Louvain community
detection + summaries → query-time PPR / subgraph retrieval.

Neo4j is an optional sink via ``KnowledgeGraphIndex.to_neo4j_rows()``;
everything here runs offline and deterministic for tests.
"""

from .community import CommunitySummarizer, detect_communities
from .extraction import (
    CooccurrenceExtractor,
    LLMEntityExtractor,
    extract_balanced_json,
)
from .graph_store import KnowledgeGraphIndex
from .models import (
    CommunityReport,
    EntityRecord,
    ExtractionResult,
    RelationRecord,
)
from .pagerank import PPRRetriever, ppr_scores
from .pipeline import Chunk, GraphRAGIndex, build_index
from .resolution import EntityResolver, normalize_name

__version__ = "0.2.0"

__all__ = [
    "Chunk",
    "CommunityReport",
    "CommunitySummarizer",
    "CooccurrenceExtractor",
    "EntityRecord",
    "EntityResolver",
    "ExtractionResult",
    "GraphRAGIndex",
    "KnowledgeGraphIndex",
    "LLMEntityExtractor",
    "PPRRetriever",
    "RelationRecord",
    "__version__",
    "build_index",
    "detect_communities",
    "extract_balanced_json",
    "normalize_name",
    "ppr_scores",
]
