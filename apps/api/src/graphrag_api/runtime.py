"""Config-driven runtime component factories.

The offline demo boots with nothing configured: the KG routes come from the
in-memory index and every optional component stays ``None``. Setting env
vars (``GRAPHRAG_QDRANT_URL``, ``GRAPHRAG_LLM_*``, ...) progressively wires
in the real stack — dense/sparse retrieval, BGE rerank, LLM generation.
Every factory degrades to ``None`` with a warning instead of failing boot,
matching the orchestrator's graceful-degradation contract.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from importlib.util import find_spec
from typing import Any

from graphrag_api.config import Settings

logger = logging.getLogger(__name__)


class SentenceTransformerEmbedder:
    """``embed``/``embed_batch`` adapter over sentence-transformers.

    The model is loaded lazily so importing this module (e.g. in tests)
    never pulls torch.
    """

    def __init__(self, *, model: str, device: str | None = None) -> None:
        self.model_name = model
        self._device = device
        self._model: Any = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers is required for embeddings. Install with "
                    "'graphrag-retrieval[embeddings]'."
                ) from exc
            self._model = SentenceTransformer(self.model_name, device=self._device)
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._ensure_model()
        return model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._ensure_model()
        return model.encode(texts, normalize_embeddings=True).tolist()


@dataclass
class RuntimeComponents:
    """Everything the composition root may optionally wire in."""

    embedder: Any | None = None
    vector: Any | None = None
    bm25: Any | None = None
    reranker: Any | None = None
    llm_client: Any | None = None
    notes: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """Truthful wiring report for logs and /readyz."""

        def status(component: Any, kind: str) -> str:
            return type(component).__name__ if component is not None else f"off({kind})"

        return {
            "vector": status(self.vector, "no qdrant_url/embedder"),
            "bm25": status(self.bm25, "no bm25_index_path"),
            "reranker": status(self.reranker, "no reranker_model"),
            "llm": status(self.llm_client, "no llm_base_url/api_key/model"),
        }


def build_embedder(settings: Settings) -> Any | None:
    """Sentence-transformers embedder, or None when not configured."""

    if not settings.embedding_model:
        return None
    try:
        return SentenceTransformerEmbedder(
            model=settings.embedding_model, device=settings.embedding_device
        )
    except Exception:
        logger.exception("embedder construction failed; continuing without embeddings")
        return None


def build_llm_client(settings: Settings) -> Any | None:
    """OpenAI-compatible client; needs base_url + api_key + model."""

    missing = [
        name
        for name, value in (
            ("GRAPHRAG_LLM_BASE_URL", settings.llm_base_url),
            ("GRAPHRAG_LLM_API_KEY", settings.llm_api_key),
            ("GRAPHRAG_LLM_MODEL", settings.llm_model),
        )
        if not value
    ]
    if not missing:
        from graphrag_api.llm import OpenAICompatLLMClient

        return OpenAICompatLLMClient(
            base_url=settings.llm_base_url or "",
            api_key=settings.llm_api_key or "",
            model=settings.llm_model or "",
        )
    logger.info("LLM wiring incomplete, missing %s — generator stays offline", missing)
    return None


def build_runtime_components(
    settings: Settings, *, embedder: Any | None = None
) -> RuntimeComponents:
    """Resolve every optional component from settings.

    ``embedder`` lets callers inject a deterministic test double; when
    omitted it is built from ``GRAPHRAG_EMBEDDING_MODEL``.
    """

    components = RuntimeComponents()
    components.embedder = embedder if embedder is not None else build_embedder(settings)

    if settings.qdrant_url and components.embedder is not None:
        from graphrag_retrieval.vector import VectorRetriever

        components.vector = VectorRetriever(
            url=settings.qdrant_url,
            collection=settings.qdrant_collection,
            embedder=components.embedder,
            dim=settings.embedding_dim,
        )
    elif settings.qdrant_url:
        components.notes.append(
            "GRAPHRAG_QDRANT_URL set but no embedder configured; vector route off"
        )

    if settings.bm25_index_path:
        from graphrag_retrieval.bm25 import BM25Retriever

        path = settings.bm25_index_path
        if path.exists():
            components.bm25 = BM25Retriever.load(path)
        else:
            components.notes.append(
                f"GRAPHRAG_BM25_INDEX_PATH {path} does not exist; bm25 route off"
            )

    if settings.reranker_model:
        if find_spec("FlagEmbedding") is None:
            components.notes.append(
                "GRAPHRAG_RERANKER_MODEL set but FlagEmbedding not installed "
                "(pip extra 'graphrag-retrieval[rerank]'); reranker off"
            )
        else:
            from graphrag_retrieval.reranker import BGEReranker

            components.reranker = BGEReranker(model_name=settings.reranker_model)

    components.llm_client = build_llm_client(settings)
    for note in components.notes:
        logger.warning("%s", note)
    logger.info("runtime wiring: %s", components.summary())
    return components
