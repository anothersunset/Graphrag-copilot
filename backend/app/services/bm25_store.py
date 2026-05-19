from __future__ import annotations

from typing import Any, Dict, List
import jieba
from rank_bm25 import BM25Okapi

class BM25Store:
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: BM25Okapi | None = None

    def _tokenize(self, text: str) -> List[str]:
        return [token.strip().lower() for token in jieba.lcut(text) if token.strip()]

    def add_documents(self, documents: List[Dict[str, Any]]):
        for doc in documents:
            content = doc.get("content", "")
            if not content:
                continue
            self.documents.append(doc)
            self.tokenized_corpus.append(self._tokenize(content))

        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)

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
        }

bm25_store = BM25Store()
