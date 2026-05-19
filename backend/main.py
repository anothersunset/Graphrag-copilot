"""GraphRAG Copilot - FastAPI 主入口"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config.settings import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("启动", settings.APP_NAME, "v" + settings.APP_VERSION)
    print("LLM 模型:", settings.LLM_MODEL)
    print("Embedding:", settings.EMBEDDING_MODEL)
    print("Neo4j:", settings.NEO4J_URI)
    yield
    try:
        from app.services.kg_service import kg_service
        kg_service.close()
    except Exception:
        pass
    print(settings.APP_NAME, "已关闭")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="面向企业知识库的多模态检索增强生成系统",
    lifespan=lifespan,
)

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
