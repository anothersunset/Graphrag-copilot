"""Typed records for the GraphRAG index layer.

These are the canonical shapes exchanged between extraction → resolution
→ graph store → community detection. They deliberately live here (not in
``graphrag_schemas``) because they are index-time artifacts; only
query-time evidence shapes belong to the shared schema package.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityRecord(BaseModel):
    """One extracted entity mention (pre-resolution)."""

    name: str
    type: str = "Entity"
    description: str = ""
    confidence: float = 0.8
    source_chunk_ids: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class RelationRecord(BaseModel):
    """One extracted relation between two entity names (pre-resolution)."""

    source: str
    target: str
    type: str = "RELATED_TO"
    description: str = ""
    confidence: float = 0.8
    source_chunk_ids: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Entities + relations extracted from one chunk (or one gleaning pass)."""

    entities: list[EntityRecord] = Field(default_factory=list)
    relations: list[RelationRecord] = Field(default_factory=list)

    def merge(self, other: ExtractionResult) -> ExtractionResult:
        return ExtractionResult(
            entities=[*self.entities, *other.entities],
            relations=[*self.relations, *other.relations],
        )


class CommunityReport(BaseModel):
    """A detected community + its LLM (or template) summary.

    Mirrors the community report used by Microsoft GraphRAG global
    search: the summary is what gets retrieved for corpus-level
    sensemaking questions, and ``entity_ids`` / ``chunk_ids`` provide
    the provenance trail back to the underlying evidence.
    """

    community_id: str
    level: int = 0
    title: str = ""
    summary: str = ""
    entity_ids: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    size: int = 0
    # degree-weighted importance of the community within the whole graph
    rank: float = 0.0
