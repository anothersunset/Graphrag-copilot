"""GraphRAG Copilot - FastAPI 主入口"""
import sys
import time
from uuid import uuid4
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager

from config.settings import settings
from app.core.logger import logger
from app.core.readiness import readiness_payload

# ---- Rate limiter (slowapi) ----
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    _SLOWAPI_AVAILABLE = True
except ImportError:
    Limiter = None  # type: ignore
    SlowAPIMiddleware = None  # type: ignore
    _SLOWAPI_AVAILABLE = False
    logger.warning("slowapi 未安装，限流被跳过")

def _rate_limit_per_min() -> int:
    try:
        return max(0, int(settings.RATE_LIMIT_PER_MIN))
    except Exception:
        return 60


if _SLOWAPI_AVAILABLE:
    default_limit = str(_rate_limit_per_min()) + "/minute"
    limiter = Limiter(key_func=get_remote_address, default_limits=[default_limit])
else:
    limiter = None


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        start = time.perf_counter()
        bound_logger = logger.bind(request_id=request_id)
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            bound_logger.exception(
                "request failed method={} path={} latency_ms={:.1f}",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        bound_logger.info(
            "request completed method={} path={} status={} latency_ms={:.1f}",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


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
    # 关键：默认限流仅在挂上 SlowAPIMiddleware 后才生效
    app.add_middleware(SlowAPIMiddleware)

app.add_middleware(RequestIdMiddleware)

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


@app.get("/readyz")
async def readiness_check():
    return readiness_payload()


from app.api.routes import router as api_router
app.include_router(api_router, prefix="/api", tags=["API"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
