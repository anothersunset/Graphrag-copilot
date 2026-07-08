from pathlib import Path
import time
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    QueryRequest,
    QueryResponse,
    VectorSearchRequest,
    DocumentResponse,
    GraphStatsResponse,
)
from app.core.constants import ALLOWED_EXTENSIONS
from app.core.logger import logger
from app.core.security import require_api_key
from config.settings import settings

router = APIRouter()


def _get_vector_store():
    from app.services.vector_store import vector_store, embedding_service
    return vector_store, embedding_service


def _get_bm25_store():
    from app.services.bm25_store import bm25_store
    return bm25_store


def _get_kg_service():
    from app.services.kg_service import kg_service
    return kg_service


def _get_doc_parser():
    from app.services.document_parser import doc_parser
    return doc_parser


def _get_llm_service():
    from app.services.llm_service import llm_service
    return llm_service


def _get_readiness():
    from app.core.readiness import observability_status, readiness_payload
    return readiness_payload, observability_status


def validate_upload_file(file: UploadFile):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type: " + suffix)

def _extract_entities_background(file_name: str, full_text: str):
    """后台执行实体抽取与知识图谱导入"""
    try:
        llm = _get_llm_service()
        extraction = llm.extract_entities(full_text[:3000])
        entities = extraction.get("entities", [])
        relations = extraction.get("relations", [])
        kg = _get_kg_service()
        stats = kg.ingest_knowledge(entities, relations)
        logger.info(
            "[BG] {}: {} entities, {} relations",
            file_name,
            stats.get("entities_created", 0),
            stats.get("relations_created", 0),
        )
    except Exception:
        logger.exception("[BG] Entity extraction failed for {}", file_name)

@router.post("/documents/upload", response_model=DocumentResponse, dependencies=[Depends(require_api_key)])
async def upload_document(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    start = time.perf_counter()
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

    dp = _get_doc_parser()
    try:
        doc_result = dp.parse(str(file_path))
    except Exception as e:
        logger.exception("Document parse failed: {}", file.filename)
        raise HTTPException(status_code=400, detail="Document parse failed: " + str(e))

    full_text = doc_result.get("content", {}).get("full_text", "")
    if not full_text:
        raise HTTPException(status_code=400, detail="Parsed document content is empty")

    chunks = dp.chunk_text(full_text)

    try:
        vs, es = _get_vector_store()
        embeddings = es.embed(chunks)
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
        vs.add_documents(documents, embeddings)
        _get_bm25_store().add_documents(documents)
    except Exception as e:
        logger.exception("Indexing failed for {}", file.filename)
        raise HTTPException(status_code=500, detail="Indexing failed: " + str(e))

    background_tasks.add_task(_extract_entities_background, file.filename, full_text)
    logger.info(
        "document upload indexed file={} bytes={} chunks={} elapsed_ms={:.1f}",
        file.filename,
        len(content),
        len(chunks),
        (time.perf_counter() - start) * 1000,
    )

    return DocumentResponse(
        file_name=file.filename,
        file_type=doc_result.get("file_type", suffix),
        content_length=len(full_text),
        chunks_created=len(chunks),
        entities_extracted=0,
        relations_extracted=0,
        document_hash=doc_result.get("file_hash"),
    )

@router.post("/query", response_model=QueryResponse, dependencies=[Depends(require_api_key)])
async def query_knowledge(request: QueryRequest):
    import asyncio
    from app.agents.orchestrator import orchestrator

    start = time.perf_counter()
    try:
        # process_query is synchronous (blocking LLM calls); run it off the
        # event loop thread so concurrent requests don't queue behind it.
        result = await asyncio.to_thread(orchestrator.process_query, request.query, request.top_k)
        logger.info(
            "query completed top_k={} sources={} confidence={:.3f} elapsed_ms={:.1f}",
            request.top_k,
            len(result.get("sources", [])),
            float(result.get("confidence", 0.0) or 0.0),
            (time.perf_counter() - start) * 1000,
        )
        return QueryResponse(
            query=result["query"],
            answer=result["answer"],
            sources=result.get("sources", []),
            analysis=result.get("analysis", {}),
            verification=result.get("verification", {}),
            trace=result.get("trace", {}),
            confidence=result.get("confidence", 0.0),
            crag_decision=result.get("crag_decision", "unknown"),
            auditor_verdict=result.get("auditor_verdict", "unknown"),
        )
    except Exception as e:
        logger.exception("Query failed elapsed_ms={:.1f}", (time.perf_counter() - start) * 1000)
        raise HTTPException(status_code=500, detail="Query failed: " + str(e))

@router.post("/query/stream", dependencies=[Depends(require_api_key)])
async def query_knowledge_stream(request: QueryRequest):
    """流式问答 SSE 端点 - 逐 token 返回"""
    import json
    from app.agents.orchestrator import stream_orchestrator

    def event_stream():
        start = time.perf_counter()
        try:
            event_count = 0
            for event in stream_orchestrator.process_query_stream(request.query, top_k=request.top_k):
                event_count += 1
                event_type = event.get("type", "message")
                yield f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            logger.info(
                "stream query completed top_k={} events={} elapsed_ms={:.1f}",
                request.top_k,
                event_count,
                (time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            logger.exception("Stream query failed elapsed_ms={:.1f}", (time.perf_counter() - start) * 1000)
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
    vs, es = _get_vector_store()
    query_embedding = es.embed_query(request.query)
    results = vs.search(query_embedding, request.top_k)
    return {"query": request.query, "results": results}

@router.get("/graph/stats", response_model=GraphStatsResponse)
async def get_graph_stats():
    stats = _get_kg_service().get_stats()
    return GraphStatsResponse(
        total_nodes=stats.get("total_nodes", 0),
        total_relations=stats.get("total_relations", 0),
        node_types=stats.get("node_types", {}),
        status=stats.get("status", "unknown"),
    )

@router.get("/graph/entity/{entity_name}")
async def get_entity_neighbors(entity_name: str, depth: int = 2):
    return _get_kg_service().search_neighbors(entity_name, depth)

@router.get("/graph/path")
async def find_entity_paths(source: str, target: str, max_depth: int = 3):
    paths = _get_kg_service().find_paths(source, target, max_depth)
    return {"source": source, "target": target, "paths": paths}

@router.get("/vector/stats")
async def get_vector_stats():
    vs, _ = _get_vector_store()
    return vs.get_stats()

@router.get("/graph")
async def get_full_graph(limit: int = 500, type: str = "all"):
    """返回全量图谱数据（节点+关系），供前端力导向图使用"""
    return _get_kg_service().get_all_graph(limit=limit, entity_type=type)

@router.get("/system/status")
async def get_system_status():
    vs, _ = _get_vector_store()
    readiness_payload, observability_status = _get_readiness()
    readiness = readiness_payload()
    return {
        "status": "running",
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "vector_store": vs.get_stats(),
        "bm25_store": _get_bm25_store().get_stats(),
        "graph_store": _get_kg_service().get_stats(),
        "auth_enabled": settings.ENABLE_AUTH,
        "rate_limit_per_min": settings.RATE_LIMIT_PER_MIN,
        "readiness": readiness["status"],
        "dependencies": readiness["dependencies"],
        "observability": observability_status(),
    }
