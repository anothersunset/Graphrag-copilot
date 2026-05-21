"""Token-budgeted semantic chunker.

Uses a regex sentence splitter (CJK + Latin aware) as the primary boundary
signal, then packs sentences into chunks under a configurable token budget,
with N-token overlap between consecutive chunks. The token counter is
dependency-injected: pass a tiktoken encoder for production accuracy, or
rely on the default whitespace-and-CJK-char heuristic for tests.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

TokenCounter = Callable[[str], int]

# CJK punctuation 。！？ + Latin sentence terminators
_SENT_RE = re.compile(r"(?<=[。！？.!?\?\n])\s+")


def _default_token_count(s: str) -> int:
    """Cheap fallback: one token per CJK char, ~one per 4 chars otherwise."""
    cjk = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
    other = len(s) - cjk
    return cjk + max(other // 4, 0)


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class SemanticChunker:
    """Sentence-aware chunker with token budget + overlap."""

    def __init__(
        self,
        *,
        max_tokens: int = 512,
        overlap_tokens: int = 64,
        token_counter: TokenCounter | None = None,
    ) -> None:
        if overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be smaller than max_tokens")
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self._count = token_counter or _default_token_count

    def _split_sentences(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        sents = [s.strip() for s in _SENT_RE.split(text) if s.strip()]
        return sents or [text]

    def _hash_chunk_id(self, doc_id: str, index: int, content: str) -> str:
        h = hashlib.sha256(f"{doc_id}|{index}|{content}".encode()).hexdigest()
        return f"{doc_id}:{index}:{h[:12]}"

    def split(
        self, *, doc_id: str, text: str, base_metadata: dict[str, Any] | None = None
    ) -> Iterator[ChunkRecord]:
        base = dict(base_metadata or {})
        sentences = self._split_sentences(text)
        buf: list[str] = []
        buf_tokens = 0
        index = 0

        def emit():
            nonlocal index, buf, buf_tokens
            if not buf:
                return None
            content = "".join(buf).strip()
            if not content:
                buf, buf_tokens = [], 0
                return None
            rec = ChunkRecord(
                chunk_id=self._hash_chunk_id(doc_id, index, content),
                doc_id=doc_id,
                content=content,
                metadata={**base, "chunk_index": index, "token_count": buf_tokens},
            )
            index += 1
            return rec

        for sent in sentences:
            sep = "" if not buf else (" " if not _is_cjk_boundary(buf[-1], sent) else "")
            piece = sep + sent
            piece_tokens = self._count(piece)
            if buf and buf_tokens + piece_tokens > self.max_tokens:
                rec = emit()
                if rec is not None:
                    yield rec
                # carry overlap from tail of previous buffer
                if self.overlap_tokens > 0:
                    carry, carry_tokens = self._tail_overlap(buf)
                    buf, buf_tokens = list(carry), carry_tokens
                else:
                    buf, buf_tokens = [], 0
                piece = sent  # no leading sep after a fresh emit
                piece_tokens = self._count(piece)
            buf.append(piece)
            buf_tokens += piece_tokens

        rec = emit()
        if rec is not None:
            yield rec

    def _tail_overlap(self, buf: list[str]) -> tuple[list[str], int]:
        carry: list[str] = []
        carry_tokens = 0
        for piece in reversed(buf):
            piece_tokens = self._count(piece)
            if carry_tokens + piece_tokens > self.overlap_tokens and carry:
                break
            carry.insert(0, piece)
            carry_tokens += piece_tokens
        return carry, carry_tokens


def _is_cjk_boundary(prev: str, nxt: str) -> bool:
    """True if both sides are CJK — no space joiner needed."""
    if not prev or not nxt:
        return False
    last = prev[-1]
    first = nxt[0]
    return ("\u4e00" <= last <= "\u9fff") and ("\u4e00" <= first <= "\u9fff")
