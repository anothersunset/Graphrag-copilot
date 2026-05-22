"""Application configuration via pydantic-settings.

All settings can be overridden via env vars prefixed with ``GRAPHRAG_`` or via
a ``.env`` file at the project root.
"""

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
    api_host: str = "0.0.0.0"  # noqa: S104  intentional bind for container
    api_port: int = 8000


settings = Settings()
