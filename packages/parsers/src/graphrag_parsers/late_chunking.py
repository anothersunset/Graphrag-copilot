"""Late Chunking (Jina, 2024).

Late Chunking encodes the full document with a long-context embedder,
then pools the token-level hidden states at chunk boundaries to produce
chunk embeddings that carry full-document context.

This module produces the chunk-boundary token spans; the actual long-
context encoder + pooling is dependency-injected so we can swap models.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .chunker import ChunkRecord, SemanticChunker


@dataclass
class LateChunkSpan:
    chunk_id: str
    doc_id: str
    token_start: int
    token_end: int
    content: str
    metadata: dict[str, Any]


class LateChunkingPlanner:
    """Plan chunk-level token spans for late-pooling embedders.

    Wraps SemanticChunker for boundary detection; emits ``LateChunkSpan``
    rows with token offsets that the long-context encoder can use to slice
    its token-level hidden states for pooling.
    """

    def __init__(
        self,
        *,
        tokenizer: Any,
        chunker: SemanticChunker | None = None,
    ) -> None:
        self.tokenizer = tokenizer
        self.chunker = chunker or SemanticChunker(
            max_tokens=512,
            overlap_tokens=64,
            token_counter=lambda s: len(tokenizer.encode(s)),
        )

    def plan(self, *, doc_id: str, text: str) -> list[LateChunkSpan]:
        chunks: list[ChunkRecord] = list(self.chunker.split(doc_id=doc_id, text=text))
        spans: list[LateChunkSpan] = []
        cursor = 0
        for chunk in chunks:
            tokens = self.tokenizer.encode(chunk.content)
            n = len(tokens)
            spans.append(
                LateChunkSpan(
                    chunk_id=chunk.chunk_id,
                    doc_id=chunk.doc_id,
                    token_start=cursor,
                    token_end=cursor + n,
                    content=chunk.content,
                    metadata=dict(chunk.metadata),
                )
            )
            # Move cursor forward by chunk minus overlap to mimic boundary stride.
            cursor += n
        return spans

    @staticmethod
    def pool(
        embeddings: Sequence[Sequence[float]],
        spans: Sequence[LateChunkSpan],
        *,
        strategy: str = "mean",
    ) -> list[list[float]]:
        """Pool token-level embeddings into chunk-level embeddings."""
        out: list[list[float]] = []
        for span in spans:
            slice_ = embeddings[span.token_start : span.token_end]
            if not slice_:
                out.append([])
                continue
            if strategy == "mean":
                dim = len(slice_[0])
                acc = [0.0] * dim
                for vec in slice_:
                    for i, v in enumerate(vec):
                        acc[i] += v
                out.append([v / len(slice_) for v in acc])
            elif strategy == "max":
                dim = len(slice_[0])
                acc = [float("-inf")] * dim
                for vec in slice_:
                    for i, v in enumerate(vec):
                        if v > acc[i]:
                            acc[i] = v
                out.append(acc)
            else:
                raise ValueError(f"unknown pooling strategy: {strategy}")
        return out
