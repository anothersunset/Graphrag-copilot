"""Entity resolution — merge mentions that refer to the same real-world entity.

The v1 pipeline MERGEd nodes by verbatim ``name``, so "Neo4j" / "neo4j" /
"Neo4j 数据库" became three disconnected nodes and multi-hop traversal
silently lost paths. Resolution runs in two stages:

1. **Normalization merge** — Unicode NFKC (full-width → half-width),
   case folding, whitespace/punctuation stripping. Deterministic, free.
2. **Similarity merge** — within the same entity type, candidates whose
   similarity clears ``threshold`` are merged. Similarity is
   dependency-injected: pass an ``embedder`` (``embed(text) -> vector``)
   to use cosine similarity over name+description; without one, falls
   back to ``difflib.SequenceMatcher`` string ratio. Type-gating keeps
   "Apple (Organization)" away from "apple (Concept)".

Merged entities keep every surface form in ``aliases``, union their
``source_chunk_ids`` (provenance survives the merge), and concatenate
distinct descriptions — descriptions later feed community summaries.
"""

from __future__ import annotations

import logging
import unicodedata
from collections.abc import Callable
from difflib import SequenceMatcher
from typing import Any

from .models import EntityRecord, ExtractionResult, RelationRecord

logger = logging.getLogger(__name__)

Embedder = Any  # exposes embed(text: str) -> list[float]
Similarity = Callable[[EntityRecord, EntityRecord], float]

_PUNCT = str.maketrans("", "", " \t\r\n·・-–—_/\\'\"“”‘’()（）[]【】<>《》,，.。:：;；!！?？")


def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFKC", name).casefold().translate(_PUNCT)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


class EntityResolver:
    def __init__(
        self,
        *,
        embedder: Embedder | None = None,
        threshold: float = 0.86,
        string_threshold: float = 0.9,
    ) -> None:
        self._embedder = embedder
        self.threshold = threshold
        self.string_threshold = string_threshold
        self._vec_cache: dict[str, list[float]] = {}

    # -- similarity -----------------------------------------------------
    def _embed(self, ent: EntityRecord) -> list[float]:
        key = f"{ent.name}|{ent.description[:80]}"
        if key not in self._vec_cache:
            self._vec_cache[key] = self._embedder.embed(f"{ent.name} {ent.description}".strip())
        return self._vec_cache[key]

    def _similar(self, a: EntityRecord, b: EntityRecord) -> bool:
        if self._embedder is not None:
            try:
                return _cosine(self._embed(a), self._embed(b)) >= self.threshold
            except Exception:
                logger.exception("embedder failed; falling back to string similarity")
        ratio = SequenceMatcher(None, normalize_name(a.name), normalize_name(b.name)).ratio()
        return ratio >= self.string_threshold

    # -- merge ----------------------------------------------------------
    @staticmethod
    def _merge_group(group: list[EntityRecord]) -> EntityRecord:
        # canonical = the most frequently-sourced mention, ties → longest name
        canonical = max(group, key=lambda e: (len(e.source_chunk_ids), len(e.name)))
        aliases: dict[str, None] = {}
        chunk_ids: dict[str, None] = {}
        descriptions: dict[str, None] = {}
        for e in group:
            if e.name != canonical.name:
                aliases.setdefault(e.name, None)
            for a in e.aliases:
                if a != canonical.name:
                    aliases.setdefault(a, None)
            for c in e.source_chunk_ids:
                chunk_ids.setdefault(c, None)
            if e.description:
                descriptions.setdefault(e.description, None)
        return EntityRecord(
            name=canonical.name,
            type=canonical.type,
            description=" ".join(descriptions),
            confidence=max(e.confidence for e in group),
            source_chunk_ids=list(chunk_ids),
            aliases=list(aliases),
        )

    def resolve(self, result: ExtractionResult) -> ExtractionResult:
        """Return a new ExtractionResult with merged entities and remapped relations."""
        # Stage 1: bucket by (type, normalized name).
        buckets: dict[tuple[str, str], list[EntityRecord]] = {}
        for e in result.entities:
            buckets.setdefault((e.type, normalize_name(e.name)), []).append(e)
        stage1 = [self._merge_group(g) for g in buckets.values()]

        # Stage 2: greedy similarity clustering within each type.
        by_type: dict[str, list[EntityRecord]] = {}
        for e in stage1:
            by_type.setdefault(e.type, []).append(e)

        merged: list[EntityRecord] = []
        for ents in by_type.values():
            clusters: list[list[EntityRecord]] = []
            for e in sorted(ents, key=lambda x: (-len(x.source_chunk_ids), x.name)):
                for cluster in clusters:
                    if self._similar(cluster[0], e):
                        cluster.append(e)
                        break
                else:
                    clusters.append([e])
            merged.extend(self._merge_group(c) for c in clusters)

        # alias → canonical name map, used to remap relations.
        canon: dict[str, str] = {}
        for e in merged:
            canon[normalize_name(e.name)] = e.name
            for a in e.aliases:
                canon[normalize_name(a)] = e.name

        relations: list[RelationRecord] = []
        seen: set[tuple[str, str, str]] = set()
        for r in result.relations:
            src = canon.get(normalize_name(r.source), r.source)
            tgt = canon.get(normalize_name(r.target), r.target)
            if src == tgt:
                continue  # merged into the same entity — self-loop, drop
            key = (src, tgt, r.type)
            if key in seen:
                # keep the first occurrence; union provenance onto it
                for kept in relations:
                    if (kept.source, kept.target, kept.type) == key:
                        for c in r.source_chunk_ids:
                            if c not in kept.source_chunk_ids:
                                kept.source_chunk_ids.append(c)
                        kept.confidence = max(kept.confidence, r.confidence)
                        break
                continue
            seen.add(key)
            relations.append(
                RelationRecord(
                    source=src,
                    target=tgt,
                    type=r.type,
                    description=r.description,
                    confidence=r.confidence,
                    source_chunk_ids=list(r.source_chunk_ids),
                )
            )

        return ExtractionResult(entities=merged, relations=relations)
