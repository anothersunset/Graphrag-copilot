"""检索适配器 — 将 backend 服务包装为 packages/graph 期望的 retriever 接口.

packages/graph 的 retriever_node 调用:
    hits = retriever.retrieve(query, top_k=top_k)
    # 返回 list[RetrievalHit] = [{"chunk_id", "source", "score", "content", "metadata"}]

本模块将 backend 的 VectorStore / BM25Store / KGService 适配为此接口。
所有服务延迟导入，避免模块加载时连接 Neo4j 或加载 embedding 模型。
"""
from __future__ import annotations

from typing import Any, Dict, List


class VectorRetriever:
    """FAISS 向量检索适配器."""

    def retrieve(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        from app.services.vector_store import vector_store, embedding_service

        query_embedding = embedding_service.embed_query(query)
        results = vector_store.search(query_embedding, top_k=top_k)
        hits = []
        for i, doc in enumerate(results):
            hits.append({
                "chunk_id": doc.get("metadata", {}).get("chunk_id", f"vec-{i}"),
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
        for i, doc in enumerate(results):
            hits.append({
                "chunk_id": doc.get("metadata", {}).get("chunk_id", f"bm25-{i}"),
                "source": "bm25",
                "score": float(doc.get("score", 0.0)),
                "content": doc.get("content", ""),
                "metadata": doc.get("metadata", {}),
            })
        return hits


class KGRetriever:
    """Neo4j 知识图谱检索适配器."""

    def retrieve(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        from app.services.kg_service import kg_service

        entities = self._extract_entities(query)
        if not entities:
            return []

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
