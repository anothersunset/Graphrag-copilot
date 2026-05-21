"""GraphRAG Copilot - FastAPI 主入口"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config.settings import settings
from app.core.logger import logger

# ---- Rate limiter (slowapi) ----
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _SLOWAPI_AVAILABLE = True
except ImportError:
    Limiter = None  # type: ignore
    _SLOWAPI_AVAILABLE = False
    logger.warning("slowapi 未安装，限流被跳过")

if _SLOWAPI_AVAILABLE:
    default_limit = str(max(0, settings.RATE_LIMIT_PER_MIN)) + "/minute"
    limiter = Limiter(key_func=get_remote_address, default_limits=[default_limit])
else:
    limiter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("启动 {} v{}", settings.APP_NAME, settings.APP_VERSION)
    logger.info("LLM 模型: {}", settings.LLM_MODEL)
    logger.info("Embedding: {}", settings.EMBEDDING_MODEL)
    logger.info("Neo4j: {}", settings.NEO4J_URI)
    logger.info("鉴权: ENABLE_AUTH={} 限流={}rpm", settings.ENABLE_AUTH, settings.RATE_LIMIT_PER_MIN)
    yield
    try:
        from app.services.kg_service import kg_service
        kg_service.close()
    except Exception:
        logger.exception("关闭 Neo4j 连接失败")
    logger.info("{} 已关闭", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="面向企业知识库的多模态检索增强生成系统",
    lifespan=lifespan,
)

if _SLOWAPI_AVAILABLE and limiter is not None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


from app.api.routes import router as api_router
app.include_router(api_router, prefix="/api", tags=["API"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
