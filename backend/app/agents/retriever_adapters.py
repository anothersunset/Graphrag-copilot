"""检索适配器 — 将 backend 服务包装为 packages/graph 期望的 retriever 接口.

packages/graph 的 retriever_node 调用:
    hits = retriever.retrieve(query, top_k=top_k)
    # 返回 list[RetrievalHit] = [{"chunk_id", "source", "score", "content", "metadata"}]

本模块将 backend 的 VectorStore / BM25Store / KGService 适配为此接口。
所有服务延迟导入，避免模块加载时连接 Neo4j 或加载 embedding 模型。
"""
from __future__ import annotations

from typing import Any, Dict, List


def _stable_chunk_id(doc: Dict[str, Any]) -> str:
    """Derive a stable chunk id from document metadata.

    Uploads (``routes.py``) stamp ``metadata["chunk_id"]`` as
    ``{file_name}#{chunk_index}``. Documents indexed before that field
    existed fall back to deriving the same format from ``file_name`` +
    ``chunk_index``, so ids survive re-indexing and are shared across the
    vector / BM25 routes. Positional ids (``vec-0``) were only unique
    within a single query result list, which made citation and recall
    metrics meaningless.
    """
    metadata = doc.get("metadata", {}) or {}
    chunk_id = metadata.get("chunk_id")
    if chunk_id:
        return str(chunk_id)
    file_name = metadata.get("file_name") or metadata.get("stored_file_name") or "unknown"
    chunk_index = metadata.get("chunk_index")
    if chunk_index is None:
        # No stable identity available — degrade to a content digest so the
        # id is at least deterministic for identical content.
        import hashlib

        digest = hashlib.md5((doc.get("content") or "").encode("utf-8")).hexdigest()[:12]
        return f"{file_name}#sha-{digest}"
    return f"{file_name}#{int(chunk_index)}"


class VectorRetriever:
    """FAISS 向量检索适配器."""

    def retrieve(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        from app.services.vector_store import vector_store, embedding_service

        query_embedding = embedding_service.embed_query(query)
        results = vector_store.search(query_embedding, top_k=top_k)
        hits = []
        for doc in results:
            hits.append({
                "chunk_id": _stable_chunk_id(doc),
                "source": "vector",
                "score": float(doc.get("score", 0.0)),
                "content": doc.get("content", ""),
                "metadata": doc.get("metadata", {}),
            })
        return hits


class BM25Retriever:
    """BM25 关键词检索适配器."""

    def retrieve(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        from app.services.bm25_store import bm25_store

        results = bm25_store.search(query, top_k=top_k)
        hits = []
        for doc in results:
            hits.append({
                "chunk_id": _stable_chunk_id(doc),
                "source": "bm25",
                "score": float(doc.get("score", 0.0)),
                "content": doc.get("content", ""),
                "metadata": doc.get("metadata", {}),
            })
        return hits


class KGRetriever:
    """Neo4j 知识图谱检索适配器.

    v3.3: 添加 5s 超时和快速跳过机制（Neo4j 不可用时自动禁用）。
    """

    def __init__(self):
        self._disabled = False  # 连续失败后禁用

    def retrieve(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if self._disabled:
            return []

        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

        entities = self._extract_entities(query)
        if not entities:
            return []

        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self._do_search, entities, query, top_k)
                return future.result(timeout=5.0)  # 5s 硬超时
        except (FuturesTimeout, Exception) as e:
            import logging
            logging.getLogger(__name__).warning("KG retriever failed/timeout: %s — disabling KG", e)
            self._disabled = True
            return []

    def _do_search(self, entities: List[str], query: str, top_k: int) -> List[Dict[str, Any]]:
        from app.services.kg_service import kg_service

        graph_results = kg_service.graph_rag_search(entities, query, depth=2)
        hits = []
        for ctx in graph_results.get("related_contexts", [])[:top_k]:
            name = ctx.get("name", "")
            entity_type = ctx.get("type", "Entity")
            distance = ctx.get("distance", 1)
            score = 0.7 / max(float(distance or 1), 1.0)
            hits.append({
                "chunk_id": f"kg-{name}",
                "source": "kg",
                "score": score,
                "content": f"实体: {name}; 类型: {entity_type}; 图谱距离: {distance}",
                "metadata": ctx,
            })
        return hits

    def _extract_entities(self, query: str) -> List[str]:
        """从查询中提取实体名称（简单策略）."""
        import jieba.posseg as pseg

        entities = []
        words = pseg.cut(query)
        for word, flag in words:
            if flag.startswith("n") or flag in ("nr", "ns", "nt", "nz"):
                if len(word) >= 2:
                    entities.append(word)

        seen = set()
        unique = []
        for e in entities:
            if e not in seen:
                seen.add(e)
                unique.append(e)

        return unique[:5]


def build_retrievers() -> Dict[str, Any]:
    """构建所有检索器实例，供 build_graph() 注入."""
    return {
        "vector": VectorRetriever(),
        "bm25": BM25Retriever(),
        "kg": KGRetriever(),
    }
