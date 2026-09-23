"""Application configuration via pydantic-settings.

All settings can be overridden via env vars prefixed with ``GRAPHRAG_`` or via
a ``.env`` file at the project root.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GRAPHRAG_",
        extra="ignore",
    )

    env: str = "dev"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    corpus_path: Path | None = None
    api_key: str | None = None
    run_store_capacity: int = 100
    run_store_ttl_seconds: int = 3600

    # -- optional runtime wiring (all default off -> offline demo mode) ----
    # OpenAI-compatible LLM (DeepSeek / Zhipu / vLLM ...). All three must be
    # set for the generator to use a real LLM instead of the skeleton answer.
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    # Qdrant dense route. Requires an embedder (see below) and a collection
    # populated by `python -m graphrag_api.ingest`.
    qdrant_url: str | None = None
    qdrant_collection: str = "graphrag_chunks"
    embedding_model: str | None = None
    embedding_dim: int = 1024  # BAAI/bge-large-zh-v1.5 native dim
    embedding_device: str | None = None
    # Sparse route: pickle written by the ingest CLI.
    bm25_index_path: Path | None = None
    # Cross-encoder rerank (needs `graphrag-retrieval[rerank]`). Off by
    # default; set to e.g. BAAI/bge-reranker-v2-m3 to enable.
    reranker_model: str | None = None


settings = Settings()
