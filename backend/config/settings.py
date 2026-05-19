"""GraphRAG Copilot - 核心配置"""
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "GraphRAG Copilot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    RAW_DIR: Path = DATA_DIR / "raw"
    PROCESSED_DIR: Path = DATA_DIR / "processed"
    VECTOR_DB_DIR: Path = DATA_DIR / "vector_db"
    GRAPH_DB_DIR: Path = DATA_DIR / "graph_db"

    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "glm-4-flash"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 4096

    ZHIPU_API_KEY: Optional[str] = None
    ZHIPU_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"

    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"
    EMBEDDING_DIMENSION: int = 512
    EMBEDDING_DEVICE: str = "cpu"

    VECTOR_STORE_TYPE: str = "faiss"
    VECTOR_SEARCH_TOP_K: int = 10
    BM25_TOP_K: int = 10

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    OCR_ENGINE: str = "paddleocr"
    ASR_MODEL: str = "base"
    ASR_DEVICE: str = "cpu"

    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    MAX_FILE_SIZE: int = 100 * 1024 * 1024

    GRAPH_SEARCH_DEPTH: int = 2
    VECTOR_WEIGHT: float = 0.55
    BM25_WEIGHT: float = 0.25
    GRAPH_WEIGHT: float = 0.20
    VERIFICATION_THRESHOLD: float = 0.8

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

settings = Settings()

for dir_path in [
    settings.DATA_DIR,
    settings.RAW_DIR,
    settings.PROCESSED_DIR,
    settings.VECTOR_DB_DIR,
    settings.GRAPH_DB_DIR,
]:
    dir_path.mkdir(parents=True, exist_ok=True)
