from __future__ import annotations

import json
import pickle
import threading
from typing import Any, Dict, List

import jieba
from rank_bm25 import BM25Okapi

from app.core.logger import logger
from config.settings import settings

_PKL_NAME = "bm25.pkl"
_DOCS_NAME = "bm25_documents.json"


class BM25Store:
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: BM25Okapi | None = None
        self._lock = threading.Lock()
        self._load()

    # ---------------------- 持久化 ----------------------
    def _pkl_path(self):
        return settings.VECTOR_DB_DIR / _PKL_NAME

    def _docs_path(self):
        return settings.VECTOR_DB_DIR / _DOCS_NAME

    def _load(self):
        pkl_path = self._pkl_path()
        docs_path = self._docs_path()
        if not pkl_path.exists() or not docs_path.exists():
            return
        try:
            with open(docs_path, "r", encoding="utf-8") as f:
                self.documents = json.load(f)
            with open(pkl_path, "rb") as f:
                payload = pickle.load(f)
            self.tokenized_corpus = payload.get("tokenized_corpus", [])
            if self.tokenized_corpus:
                self.bm25 = BM25Okapi(self.tokenized_corpus)
            logger.info("BM25 已恢复 {} 条文档", len(self.documents))
        except Exception:
            logger.exception("BM25 持久化文件加载失败，重置为空")
            self.documents = []
            self.tokenized_corpus = []
            self.bm25 = None

    def _save(self):
        """必须在 self._lock 保护下调用"""
        try:
            settings.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
            with open(self._docs_path(), "w", encoding="utf-8") as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)
            with open(self._pkl_path(), "wb") as f:
                pickle.dump({"tokenized_corpus": self.tokenized_corpus}, f)
        except Exception:
            logger.exception("BM25 落盘失败")

    # ---------------------- 分词 / 写入 / 检索 ----------------------
    def _tokenize(self, text: str) -> List[str]:
        return [token.strip().lower() for token in jieba.lcut(text) if token.strip()]

    def add_documents(self, documents: List[Dict[str, Any]]):
        with self._lock:
            for doc in documents:
                content = doc.get("content", "")
                if not content:
                    continue
                self.documents.append(doc)
                self.tokenized_corpus.append(self._tokenize(content))

            if self.tokenized_corpus:
                self.bm25 = BM25Okapi(self.tokenized_corpus)

            self._save()

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if not self.bm25 or not self.documents:
            return []

        query_tokens = self._tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        max_score = max([score for _, score in ranked], default=1.0) or 1.0

        for idx, score in ranked:
            doc = self.documents[idx].copy()
            doc["score"] = float(score / max_score)
            results.append(doc)

        return results

    def get_stats(self) -> Dict[str, Any]:
        return {
            "type": "bm25",
            "total_documents": len(self.documents),
            "ready": self.bm25 is not None,
            "persisted": self._pkl_path().exists() and self._docs_path().exists(),
        }

bm25_store = BM25Store()
