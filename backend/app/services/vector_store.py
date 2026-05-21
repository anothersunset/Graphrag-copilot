"""GraphRAG Copilot - FAISS 向量存储 + Embedding"""
from typing import List, Dict, Any
import json
import threading
import numpy as np
from config.settings import settings
from app.core.logger import logger

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS 未安装，向量检索功能将不可用")

class VectorStore:
    def __init__(self, store_type: str = None):
        self.store_type = store_type or settings.VECTOR_STORE_TYPE
        self.dimension = settings.EMBEDDING_DIMENSION
        self.index = None
        self.documents = []
        self._lock = threading.Lock()
        self._init_store()

    def _init_store(self):
        if self.store_type == "faiss":
            self._init_faiss()
        else:
            raise ValueError("不支持的向量存储类型: " + str(self.store_type))

    def _init_faiss(self):
        if not FAISS_AVAILABLE:
            return

        index_path = settings.VECTOR_DB_DIR / "faiss.index"
        docs_path = settings.VECTOR_DB_DIR / "documents.json"

        if index_path.exists() and docs_path.exists():
            try:
                self.index = faiss.read_index(str(index_path))
                with open(docs_path, "r", encoding="utf-8") as f:
                    self.documents = json.load(f)
            except Exception:
                logger.exception("FAISS 索引加载失败，重建空索引")
                self.index = faiss.IndexFlatIP(self.dimension)
                self.documents = []
        else:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.documents = []

    def add_documents(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]):
        if not FAISS_AVAILABLE or self.index is None:
            return

        if len(documents) != len(embeddings):
            raise ValueError("文档数量和向量数量必须一致")

        embeddings_array = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(embeddings_array)

        with self._lock:
            self.index.add(embeddings_array)
            for doc in documents:
                self.documents.append({
                    "id": doc.get("id", len(self.documents)),
                    "content": doc.get("content", ""),
                    "metadata": doc.get("metadata", {}),
                })
            self._save()

    def search(self, query_embedding: List[float], top_k: int = None) -> List[Dict[str, Any]]:
        if not FAISS_AVAILABLE or self.index is None or self.index.ntotal == 0:
            return []

        top_k = top_k or settings.VECTOR_SEARCH_TOP_K
        query_array = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_array)

        scores, indices = self.index.search(query_array, min(top_k, self.index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if 0 <= idx < len(self.documents):
                doc = self.documents[idx].copy()
                doc["score"] = float(score)
                results.append(doc)
        return results

    def _save(self):
        """必须在 self._lock 保护下调用"""
        if not FAISS_AVAILABLE or self.index is None:
            return

        index_path = settings.VECTOR_DB_DIR / "faiss.index"
        docs_path = settings.VECTOR_DB_DIR / "documents.json"

        try:
            faiss.write_index(self.index, str(index_path))
            with open(docs_path, "w", encoding="utf-8") as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)
        except Exception:
            logger.exception("FAISS 索引落盘失败")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "type": self.store_type,
            "total_vectors": self.index.ntotal if self.index else 0,
            "dimension": self.dimension,
            "total_documents": len(self.documents),
        }

class EmbeddingService:
    def __init__(self):
        self.model = None
        self.use_tfidf = True
        self._init_model()

    def _init_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(
                settings.EMBEDDING_MODEL,
                device=settings.EMBEDDING_DEVICE,
            )
            self.use_tfidf = False
        except Exception:
            logger.exception("Embedding 模型加载失败，使用 hash 备选")
            self.model = None
            self.use_tfidf = True

    def embed(self, texts: List[str]) -> List[List[float]]:
        if self.model is not None and not self.use_tfidf:
            embeddings = self.model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=len(texts) > 10,
            )
            return embeddings.tolist()
        return self._hash_embed(texts)

    def _hash_embed(self, texts: List[str]) -> List[List[float]]:
        import hashlib
        embeddings = []
        for text in texts:
            h = hashlib.md5(text.encode()).digest()
            vec = np.frombuffer(h, dtype=np.uint8).astype(np.float32)
            vec = np.tile(vec, 512 // len(vec) + 1)[:512]
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            embeddings.append(vec.tolist())
        return embeddings

    def embed_query(self, query: str) -> List[float]:
        return self.embed([query])[0]

vector_store = VectorStore()
embedding_service = EmbeddingService()
