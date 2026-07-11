"""BGE-Reranker-v2-m3 cross-encoder wrapper.

Usage:
    reranker = BGEReranker()
    top5 = reranker.rerank(query, fused_hits, top_k=5)

The scorer is dependency-injected so tests can pass a deterministic
function without loading the actual 568M-parameter model.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from importlib import import_module
from typing import Any, Protocol, cast

from .base import RetrievalHit, _normalise_hit

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"

Scorer = Callable[[str, Sequence[str]], list[float]]


class RerankerModel(Protocol):
    def compute_score(
        self, pairs: Sequence[Sequence[str]], *, normalize: bool
    ) -> float | Sequence[float]: ...


class BGEReranker:
    """Cross-encoder reranker over a fused candidate list."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL,
        scorer: Scorer | None = None,
        batch_size: int = 16,
        use_fp16: bool = True,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.use_fp16 = use_fp16
        self._scorer = scorer
        self._model: RerankerModel | None = None

    def _load(self) -> RerankerModel:
        if self._model is not None:
            return self._model
        try:
            module = import_module("FlagEmbedding")
            model_class = module.FlagReranker
        except (ImportError, AttributeError) as e:
            raise RuntimeError(
                "BGEReranker requires FlagEmbedding. Install with 'graphrag-retrieval[rerank]'."
            ) from e
        self._model = cast(
            RerankerModel,
            model_class(self.model_name, use_fp16=self.use_fp16),
        )
        return self._model

    def _score(self, query: str, contents: Sequence[str]) -> list[float]:
        if self._scorer is not None:
            return list(self._scorer(query, contents))
        model = self._load()
        pairs = [[query, c] for c in contents]
        out: list[float] = []
        for start in range(0, len(pairs), self.batch_size):
            batch = pairs[start : start + self.batch_size]
            scores = model.compute_score(batch, normalize=True)
            if isinstance(scores, (int, float)):
                out.append(float(scores))
            else:
                out.extend(float(s) for s in scores)
        return out

    def rerank(
        self,
        query: str,
        hits: Sequence[Mapping[str, Any]],
        *,
        top_k: int,
    ) -> list[RetrievalHit]:
        if not hits:
            return []
        contents = [h.get("content", "") for h in hits]
        try:
            scores = self._score(query, contents)
        except Exception:
            logger.exception("rerank failed; returning input slice")
            return [_normalise_hit(hit) for hit in hits[:top_k]]

        if len(scores) != len(hits):
            logger.error(
                "reranker returned %d scores for %d hits; returning input slice",
                len(scores),
                len(hits),
            )
            return [_normalise_hit(hit) for hit in hits[:top_k]]

        scored: list[RetrievalHit] = []
        for hit, s in zip(hits, scores):
            h = _normalise_hit(hit)
            h["rerank_score"] = float(s)
            scored.append(h)
        def rerank_value(hit: RetrievalHit) -> float:
            score = hit.get("rerank_score")
            return float(score) if score is not None else 0.0

        scored.sort(key=rerank_value, reverse=True)
        return scored[:top_k]
