from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List

import jieba
from rank_bm25 import BM25Okapi

from app.core.logger import logger
from config.settings import settings

_CORPUS_NAME = "bm25_corpus.json"
_DOCS_NAME = "bm25_documents.json"
_PKL_NAME = "bm25.pkl"  # 旧格式，仅向后兼容读取


class BM25Store:
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: BM25Okapi | None = None
        self._lock = threading.Lock()
        self._load()

    # ---------------------- 持久化 ----------------------
    def _corpus_path(self):
        return settings.VECTOR_DB_DIR / _CORPUS_NAME

    def _docs_path(self):
        return settings.VECTOR_DB_DIR / _DOCS_NAME

    def _pkl_path(self):
        return settings.VECTOR_DB_DIR / _PKL_NAME

    def _load(self):
        corpus_path = self._corpus_path()
        docs_path = self._docs_path()
        pkl_path = self._pkl_path()
        if not docs_path.exists():
            return
        try:
            with open(docs_path, "r", encoding="utf-8") as f:
                self.documents = json.load(f)
            if corpus_path.exists():
                with open(corpus_path, "r", encoding="utf-8") as f:
                    self.tokenized_corpus = json.load(f)
            elif pkl_path.exists():
                # 向后兼容：迁移旧 pickle 格式
                import pickle
                with open(pkl_path, "rb") as f:
                    payload = pickle.load(f)
                self.tokenized_corpus = payload.get("tokenized_corpus", [])
                # 立即写为新 JSON 格式并删除旧 pkl
                self._save_corpus()
                try:
                    os.remove(pkl_path)
                except OSError:
                    pass
                logger.info("BM25 已从 pickle 迁移到 JSON 格式")
            if self.tokenized_corpus:
                self.bm25 = BM25Okapi(self.tokenized_corpus)
            logger.info("BM25 已恢复 {} 条文档", len(self.documents))
        except Exception:
            logger.exception("BM25 持久化文件加载失败，重置为空")
            self.documents = []
            self.tokenized_corpus = []
            self.bm25 = None

    def _save_corpus(self):
        """持久化 tokenized_corpus 为 JSON（必须在 self._lock 保护下调用）"""
        with open(self._corpus_path(), "w", encoding="utf-8") as f:
            json.dump(self.tokenized_corpus, f, ensure_ascii=False)

    def _save(self):
        """必须在 self._lock 保护下调用"""
        try:
            settings.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
            # 原子写入：先写临时文件再 rename
            docs_tmp = self._docs_path().with_suffix(".json.tmp")
            with open(docs_tmp, "w", encoding="utf-8") as f:
                json.dump(self.documents, f, ensure_ascii=False, indent=2)
            os.replace(docs_tmp, self._docs_path())
            self._save_corpus()
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
        with self._lock:
            if not self.bm25 or not self.documents:
                return []

            query_tokens = self._tokenize(query)
            scores = self.bm25.get_scores(query_tokens)
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

            results = []
            max_score = max([score for _, score in ranked], default=1.0) or 1.0

            for idx, score in ranked:
                if idx < len(self.documents):
                    doc = self.documents[idx].copy()
                    doc["score"] = max(0.0, float(score / max_score))
                    results.append(doc)

        return results

    def get_stats(self) -> Dict[str, Any]:
        return {
            "type": "bm25",
            "total_documents": len(self.documents),
            "ready": self.bm25 is not None,
            "persisted": self._corpus_path().exists() and self._docs_path().exists(),
        }

bm25_store = BM25Store()
