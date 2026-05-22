"""Header-aware Markdown splitter.

Walks the document line-by-line, tracks the current heading stack, and
emits one ChunkRecord per heading section (further sub-split by
SemanticChunker if a section exceeds the token budget). Fenced code
blocks and pipe tables are preserved as a single atomic block (never
split mid-fence).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

from .chunker import ChunkRecord, SemanticChunker

HEADER_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*```")
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")


@dataclass
class _Section:
    breadcrumbs: list[str]
    lines: list[str]


class MarkdownSplitter:
    """Split a Markdown document while preserving heading breadcrumbs."""

    def __init__(
        self,
        *,
        max_tokens: int = 512,
        overlap_tokens: int = 64,
    ) -> None:
        self._chunker = SemanticChunker(max_tokens=max_tokens, overlap_tokens=overlap_tokens)

    def split(self, *, doc_id: str, text: str) -> Iterator[ChunkRecord]:
        for section in self._iter_sections(text):
            content = "\n".join(section.lines).strip()
            if not content:
                continue
            crumbs = " > ".join(section.breadcrumbs) if section.breadcrumbs else ""
            yield from self._chunker.split(
                doc_id=doc_id,
                text=content,
                base_metadata={
                    "breadcrumbs": crumbs,
                    "heading_depth": len(section.breadcrumbs),
                },
            )

    def _iter_sections(self, text: str) -> Iterator[_Section]:
        stack: list[tuple[int, str]] = []
        current_lines: list[str] = []
        in_fence = False

        def crumbs() -> list[str]:
            return [name for _, name in stack]

        def flush_section() -> _Section | None:
            if not current_lines:
                return None
            return _Section(breadcrumbs=crumbs(), lines=list(current_lines))

        for line in text.splitlines():
            if FENCE_RE.match(line):
                in_fence = not in_fence
                current_lines.append(line)
                continue
            if in_fence:
                current_lines.append(line)
                continue
            m = HEADER_RE.match(line)
            if m:
                sec = flush_section()
                if sec is not None:
                    yield sec
                current_lines = []
                depth = len(m.group(1))
                name = m.group(2).strip()
                stack = [(d, n) for d, n in stack if d < depth]
                stack.append((depth, name))
                continue
            current_lines.append(line)

        sec = flush_section()
        if sec is not None:
            yield sec
