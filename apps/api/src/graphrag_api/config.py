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


settings = Settings()
