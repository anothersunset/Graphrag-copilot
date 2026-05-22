"""Sentence-level claim model and helpers.

A Claim is a sentence (or sentence-like span) of the generated answer
bound to the set of evidence ids that support it. This lets the auditor
emit per-sentence provenance (句级溯源) instead of one flat
``cited_chunk_ids`` list, and lets the eval layer compute Provenance
Sufficiency at sentence granularity.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, Field


class Claim(BaseModel):
    """One sentence of the answer + its supporting evidence ids."""

    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    # "supported" | "unsupported" | "partial"
    support: str = "supported"

    def is_supported(self) -> bool:
        return self.support == "supported" and bool(self.evidence_ids)


# Sentence terminators — Chinese + English + Japanese. The second
# alternative is a zero-width lookbehind that handles CJK punctuation
# not followed by whitespace (e.g. "。It uses Neo4j").
_TERMINATORS = re.compile(r"(?<=[\u3002\uFF01\uFF1F!?\.])\s+|(?<=[\u3002\uFF01\uFF1F])")
_FENCE = re.compile(r"(```.*?```|\$\$.*?\$\$)", re.DOTALL)


def _split_sentences(text: str) -> list[str]:
    """Terminator-based split for a fence-free chunk; strips and drops empties."""
    return [p for p in (p.strip() for p in _TERMINATORS.split(text)) if p]


def split_into_claims(answer: str) -> list[str]:
    """Segment an answer into sentence-ish spans.

    Code blocks and display-math blocks are preserved as single spans so
    we never split mid-equation or mid-code, AND they emit as their own
    claim (they are not glued to adjacent prose). This is what allows
    the auditor to attribute a fenced block to its own evidence row.
    """
    if not answer or not answer.strip():
        return []

    parts: list[str] = []
    pos = 0
    for m in _FENCE.finditer(answer):
        if m.start() > pos:
            parts.extend(_split_sentences(answer[pos : m.start()]))
        fence_span = m.group(0).strip()
        if fence_span:
            parts.append(fence_span)
        pos = m.end()
    if pos < len(answer):
        parts.extend(_split_sentences(answer[pos:]))
    return parts


def coerce_claims(value: Any) -> list[Claim]:
    """Normalize the various shapes a DSPy Signature might emit.

    Accepts list[Claim], list[dict], list[str], a JSON-string of any of
    those, or None. Anything unparseable becomes an empty list — the
    caller should fall back to the sentence heuristic.
    """
    if value is None or value == "":
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return []
    if not isinstance(value, Iterable):
        return []
    out: list[Claim] = []
    for item in value:  # type: ignore[assignment]
        if isinstance(item, Claim):
            out.append(item)
        elif isinstance(item, dict):
            try:
                out.append(Claim(**item))
            except Exception:
                continue
        elif isinstance(item, str):
            out.append(Claim(text=item, evidence_ids=[], support="unsupported"))
    return out


def heuristic_claims(
    answer: str,
    *,
    cited_chunk_ids: list[str],
    contexts: list[dict] | None = None,
    min_overlap: int = 2,
) -> list[Claim]:
    """Build claims when DSPy didn't (or couldn't) provide them.

    Each sentence is mapped to the subset of ``cited_chunk_ids`` whose
    context content shares at least ``min_overlap`` significant tokens
    with the sentence. If we have no context corpus, fall back to
    "every sentence cites every cited chunk" which is at least
    consistent with the answer-level cited_chunk_ids signal.
    """
    sentences = split_into_claims(answer)
    if not sentences:
        return []

    by_id: dict[str, str] = {}
    if contexts:
        for h in contexts:
            cid = h.get("chunk_id")
            if cid:
                by_id[cid] = h.get("content", "")

    claims: list[Claim] = []
    for sent in sentences:
        sent_tokens = _tokens(sent)
        if not by_id:
            claims.append(
                Claim(
                    text=sent,
                    evidence_ids=list(cited_chunk_ids),
                    support="supported" if cited_chunk_ids else "unsupported",
                )
            )
            continue
        matched = [
            cid
            for cid in cited_chunk_ids
            if len(sent_tokens & _tokens(by_id.get(cid, ""))) >= min_overlap
        ]
        claims.append(
            Claim(
                text=sent,
                evidence_ids=matched,
                support="supported" if matched else "unsupported",
            )
        )
    return claims


_TOKEN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z][A-Za-z0-9_]+")


def _tokens(s: str) -> set[str]:
    if not s:
        return set()
    return {t.lower() for t in _TOKEN.findall(s) if len(t) >= 2 or _is_cjk(t)}


def _is_cjk(t: str) -> bool:
    return len(t) == 1 and "\u4e00" <= t <= "\u9fff"
