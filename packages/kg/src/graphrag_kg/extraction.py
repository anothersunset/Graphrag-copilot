"""Entity / relation extraction with multi-round gleaning.

Two extractors, one contract (``extract(chunk_id, text) -> ExtractionResult``):

* ``LLMEntityExtractor`` — LLM-backed extraction with the **gleaning
  loop** from Microsoft GraphRAG (Edge et al., 2024): after the first
  pass, the model is re-prompted up to ``max_gleanings`` times with
  "MANY entities were missed" to recover entities that a single pass
  systematically drops (the paper reports gleaning is what lets a
  smaller/cheaper model match a larger one on extraction recall).
  The LLM is dependency-injected as a plain callable so tests and
  offline runs need no API key.

* ``CooccurrenceExtractor`` — deterministic, zero-dependency fallback:
  noun/proper-noun terms become entities and sentence-window
  co-occurrence becomes ``CO_OCCURS_WITH`` relations. Quality is far
  below the LLM path, but it keeps the whole index pipeline runnable
  (and testable) without any external service — the same graceful-
  degradation stance the rest of the project takes.

JSON robustness: LLM output is parsed with a brace-depth scanner rather
than a greedy regex — reasoning models often emit thinking tokens and
multiple JSON objects, and ``\\{[\\s\\S]*\\}`` silently spans them all.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from collections.abc import Callable
from itertools import combinations

from .models import EntityRecord, ExtractionResult, RelationRecord

logger = logging.getLogger(__name__)

# (system, user) -> raw completion text
ChatFn = Callable[[str, str], str]

ENTITY_TYPES = (
    "Person", "Organization", "Product", "Technology",
    "Concept", "Document", "Event", "Location",
)
RELATION_TYPES = (
    "USES", "BELONGS_TO", "DEPENDS_ON", "RELATED_TO", "CAUSES",
    "PART_OF", "CONTAINS", "CREATED", "WORKS_FOR", "COMPARES_WITH",
)

_SYSTEM_PROMPT = (
    "你是知识图谱抽取专家。从文本中抽取实体和关系，只输出一个 JSON 对象，不要输出任何其他内容。\n"
    "每个实体附带一句 description（用于后续实体消歧与社区摘要）。\n"
    "输出格式:\n"
    '{"entities": [{"name": "...", "type": "' + "|".join(ENTITY_TYPES) + '", '
    '"description": "...", "confidence": 0.0}], '
    '"relations": [{"source": "...", "target": "...", "type": "' + "|".join(RELATION_TYPES) + '", '
    '"description": "...", "confidence": 0.0}]}'
)

_GLEANING_PROMPT = (
    "上一轮抽取遗漏了很多实体和关系。请再仔细读一遍文本，"
    "只输出上一轮 **没有** 抽到的新实体和新关系，格式同前。"
    "如果确实没有遗漏，输出 {\"entities\": [], \"relations\": []}。\n\n"
    "已抽取的实体: {known}\n\n文本:\n{text}"
)


def extract_balanced_json(text: str) -> dict:
    """Return the first balanced top-level JSON object in ``text``.

    Brace counting honours JSON string literals and escapes, so braces
    inside values don't corrupt the depth. Returns {} when nothing
    parseable is found.
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = in_str
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break  # malformed — try the next '{'
        start = text.find("{", start + 1)
    return {}


def _coerce_result(payload: dict, *, chunk_id: str) -> ExtractionResult:
    entities: list[EntityRecord] = []
    for e in payload.get("entities", []) or []:
        if not isinstance(e, dict) or not e.get("name"):
            continue
        etype = e.get("type", "Concept")
        entities.append(
            EntityRecord(
                name=str(e["name"]).strip(),
                type=etype if etype in ENTITY_TYPES else "Concept",
                description=str(e.get("description", "") or ""),
                confidence=float(e.get("confidence", 0.8) or 0.8),
                source_chunk_ids=[chunk_id],
            )
        )
    relations: list[RelationRecord] = []
    for r in payload.get("relations", []) or []:
        if not isinstance(r, dict) or not r.get("source") or not r.get("target"):
            continue
        rtype = r.get("type", "RELATED_TO")
        relations.append(
            RelationRecord(
                source=str(r["source"]).strip(),
                target=str(r["target"]).strip(),
                type=rtype if rtype in RELATION_TYPES else "RELATED_TO",
                description=str(r.get("description", "") or ""),
                confidence=float(r.get("confidence", 0.8) or 0.8),
                source_chunk_ids=[chunk_id],
            )
        )
    return ExtractionResult(entities=entities, relations=relations)


class LLMEntityExtractor:
    """LLM extraction with gleaning; processes one chunk per call.

    Chunks should come from ``graphrag_parsers.SemanticChunker`` — the
    old v1 pipeline truncated每份文档到前 3000 字符, which is exactly the
    failure mode chunk-wise extraction removes.
    """

    def __init__(self, *, llm: ChatFn, max_gleanings: int = 1) -> None:
        self._llm = llm
        self.max_gleanings = max(0, max_gleanings)

    def extract(self, chunk_id: str, text: str) -> ExtractionResult:
        if not text.strip():
            return ExtractionResult()
        try:
            raw = self._llm(_SYSTEM_PROMPT, f"请抽取以下文本中的实体和关系:\n\n{text}")
        except Exception:
            logger.exception("extraction failed for chunk %s", chunk_id)
            return ExtractionResult()
        result = _coerce_result(extract_balanced_json(raw), chunk_id=chunk_id)

        for _ in range(self.max_gleanings):
            known = ", ".join(e.name for e in result.entities) or "(无)"
            try:
                raw = self._llm(
                    _SYSTEM_PROMPT,
                    _GLEANING_PROMPT.replace("{known}", known).replace("{text}", text),
                )
            except Exception:
                logger.exception("gleaning pass failed for chunk %s", chunk_id)
                break
            extra = _coerce_result(extract_balanced_json(raw), chunk_id=chunk_id)
            new_entities = [
                e for e in extra.entities
                if e.name.lower() not in {x.name.lower() for x in result.entities}
            ]
            if not new_entities and not extra.relations:
                break  # model says nothing was missed — stop early
            result = result.merge(ExtractionResult(entities=new_entities, relations=extra.relations))
        return result


_LATIN_TERM = re.compile(r"\b[A-Za-z][A-Za-z0-9_\-]*[A-Z0-9][A-Za-z0-9_\-]*\b|\b[A-Z][a-z]{2,}\b")
_SENT_SPLIT = re.compile(r"(?<=[。！？.!?\n])")


class CooccurrenceExtractor:
    """Deterministic no-LLM extractor (graceful degradation path)."""

    def __init__(self, *, min_term_len: int = 2, max_entities_per_chunk: int = 12) -> None:
        self.min_term_len = min_term_len
        self.max_entities = max_entities_per_chunk

    def _terms(self, sentence: str) -> list[str]:
        terms = list(_LATIN_TERM.findall(sentence))
        try:
            import jieba.posseg as pseg

            terms.extend(
                w for w, flag in pseg.cut(sentence)
                if flag.startswith("n") and len(w) >= self.min_term_len
            )
        except ImportError:
            terms.extend(re.findall(r"[一-鿿]{2,6}", sentence))
        return terms

    def extract(self, chunk_id: str, text: str) -> ExtractionResult:
        if not text.strip():
            return ExtractionResult()
        sentences = [s for s in _SENT_SPLIT.split(text) if s.strip()]
        freq: Counter[str] = Counter()
        pair_freq: Counter[tuple[str, str]] = Counter()
        for sent in sentences:
            terms = list(dict.fromkeys(self._terms(sent)))
            freq.update(terms)
            for a, b in combinations(sorted(terms), 2):
                pair_freq[(a, b)] += 1

        top_terms = {t for t, _ in freq.most_common(self.max_entities)}
        entities = [
            EntityRecord(
                name=t,
                type="Concept",
                confidence=min(0.5 + 0.1 * freq[t], 0.9),
                source_chunk_ids=[chunk_id],
            )
            for t in sorted(top_terms)
        ]
        relations = [
            RelationRecord(
                source=a,
                target=b,
                type="RELATED_TO",
                description="sentence co-occurrence",
                confidence=min(0.3 + 0.1 * n, 0.8),
                source_chunk_ids=[chunk_id],
            )
            for (a, b), n in pair_freq.most_common()
            if a in top_terms and b in top_terms
        ]
        return ExtractionResult(entities=entities, relations=relations)
