from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    QueryRequest,
    QueryResponse,
    VectorSearchRequest,
    DocumentResponse,
    GraphStatsResponse,
)
from app.core.constants import ALLOWED_EXTENSIONS
from app.services.vector_store import vector_store, embedding_service
from app.services.bm25_store import bm25_store
from app.services.kg_service import kg_service
from app.services.document_parser import doc_parser
from app.services.llm_service import llm_service
from app.agents.orchestrator import orchestrator, stream_orchestrator
from config.settings import settings

router = APIRouter()

def validate_upload_file(file: UploadFile):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type: " + suffix)

def _extract_entities_background(file_name: str, full_text: str):
    """后台执行实体抽取与知识图谱导入"""
    try:
        extraction = llm_service.extract_entities(full_text[:3000])
        entities = extraction.get("entities", [])
        relations = extraction.get("relations", [])
        stats = kg_service.ingest_knowledge(entities, relations)
        print(f"[BG] {file_name}: {stats.get('entities_created', 0)} entities, {stats.get('relations_created', 0)} relations")
    except Exception as e:
        print(f"[BG] Entity extraction failed for {file_name}: {e}")

@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    validate_upload_file(file)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Uploaded file is too large")

    suffix = Path(file.filename).suffix.lower()
    safe_name = uuid4().hex + suffix
    file_path = settings.RAW_DIR / safe_name

    with open(file_path, "wb") as f:
        f.write(content)

    try:
        doc_result = doc_parser.parse(str(file_path))
    except Exception as e:
        raise HTTPException(status_code=400, detail="Document parse failed: " + str(e))

    full_text = doc_result.get("content", {}).get("full_text", "")
    if not full_text:
        raise HTTPException(status_code=400, detail="Parsed document content is empty")

    chunks = doc_parser.chunk_text(full_text)

    try:
        embeddings = embedding_service.embed(chunks)
        documents = [
            {
                "content": chunk,
                "metadata": {
                    "file_name": file.filename,
                    "stored_file_name": safe_name,
                    "chunk_index": i,
                    "file_hash": doc_result.get("file_hash"),
                    "source_type": doc_result.get("file_type", suffix),
                },
            }
            for i, chunk in enumerate(chunks)
        ]
        vector_store.add_documents(documents, embeddings)
        bm25_store.add_documents(documents)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Indexing failed: " + str(e))

    # 实体抽取改为后台执行，不阻塞上传响应
    background_tasks.add_task(_extract_entities_background, file.filename, full_text)

    return DocumentResponse(
        file_name=file.filename,
        file_type=doc_result.get("file_type", suffix),
        content_length=len(full_text),
        chunks_created=len(chunks),
        entities_extracted=0,  # 后台异步处理，响应中返回 0
        relations_extracted=0,
        document_hash=doc_result.get("file_hash"),
    )

@router.post("/query", response_model=QueryResponse)
async def query_knowledge(request: QueryRequest):
    try:
        result = orchestrator.process_query(request.query, top_k=request.top_k)
        return QueryResponse(
            query=result["query"],
            answer=result["answer"],
            sources=result.get("sources", []),
            analysis=result.get("analysis", {}),
            verification=result.get("verification", {}),
            trace=result.get("trace", {}),
            confidence=result.get("confidence", 0.0),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Query failed: " + str(e))

@router.post("/query/stream")
async def query_knowledge_stream(request: QueryRequest):
    """流式问答 SSE 端点 - 逐 token 返回"""
    import json

    def event_stream():
        try:
            for event in stream_orchestrator.process_query_stream(request.query, top_k=request.top_k):
                event_type = event.get("type", "message")
                yield f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.post("/vector/search")
async def search_vector(request: VectorSearchRequest):
    query_embedding = embedding_service.embed_query(request.query)
    results = vector_store.search(query_embedding, request.top_k)
    return {"query": request.query, "results": results}

@router.get("/graph/stats", response_model=GraphStatsResponse)
async def get_graph_stats():
    stats = kg_service.get_stats()
    return GraphStatsResponse(
        total_nodes=stats.get("total_nodes", 0),
        total_relations=stats.get("total_relations", 0),
        node_types=stats.get("node_types", {}),
        status=stats.get("status", "unknown"),
    )

@router.get("/graph/entity/{entity_name}")
async def get_entity_neighbors(entity_name: str, depth: int = 2):
    return kg_service.search_neighbors(entity_name, depth)

@router.get("/graph/path")
async def find_entity_paths(source: str, target: str, max_depth: int = 3):
    paths = kg_service.find_paths(source, target, max_depth)
    return {"source": source, "target": target, "paths": paths}

@router.get("/vector/stats")
async def get_vector_stats():
    return vector_store.get_stats()

@router.get("/system/status")
async def get_system_status():
    return {
        "status": "running",
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "vector_store": vector_store.get_stats(),
        "bm25_store": bm25_store.get_stats(),
        "graph_store": kg_service.get_stats(),
    }
