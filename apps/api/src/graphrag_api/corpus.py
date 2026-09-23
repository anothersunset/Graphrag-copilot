"""Corpus loading shared by the API lifespan and the ingest CLI."""

from __future__ import annotations

import json
from pathlib import Path

from graphrag_kg import Chunk


def load_corpus(path: Path) -> list[Chunk]:
    """Load ``.md``/``.txt``/``.jsonl`` files as document-level chunks."""
    if not path.exists():
        raise FileNotFoundError(f"corpus path does not exist: {path}")
    files = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
    chunks: list[Chunk] = []
    for file in files:
        suffix = file.suffix.lower()
        if suffix in {".md", ".txt"}:
            content = file.read_text(encoding="utf-8").strip()
            if content:
                chunks.append(
                    Chunk(str(file.relative_to(path) if path.is_dir() else file.name), content)
                )
        elif suffix == ".jsonl":
            for line_no, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                content = str(row.get("content") or row.get("text") or "").strip()
                if content:
                    chunk_id = str(row.get("chunk_id") or f"{file.name}:{line_no}")
                    chunks.append(Chunk(chunk_id, content))
    if not chunks:
        raise ValueError(f"corpus contains no supported non-empty documents: {path}")
    return chunks
