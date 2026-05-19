"""GraphRAG Copilot - API Schema"""
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)

class VectorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)

class Evidence(BaseModel):
    content: str
    source: str
    type: Literal["vector", "graph", "bm25"]
    score: Optional[float] = None
    fusion_score: Optional[float] = None
    matched_by: List[str] = []
    metadata: Dict[str, Any] = {}

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    analysis: Dict[str, Any]
    verification: Dict[str, Any]
    trace: Dict[str, Any] = {}
    confidence: float = 0.0

class DocumentResponse(BaseModel):
    file_name: str
    file_type: str
    content_length: int
    chunks_created: int
    entities_extracted: int
    relations_extracted: int = 0
    document_hash: Optional[str] = None

class GraphStatsResponse(BaseModel):
    total_nodes: int = 0
    total_relations: int = 0
    node_types: Dict[str, int] = {}
    status: str = "unknown"
