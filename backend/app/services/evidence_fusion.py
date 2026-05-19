from __future__ import annotations

from typing import Any, Dict, List
import hashlib
from config.settings import settings

class EvidenceFusionService:
    def _fingerprint(self, content: str) -> str:
        normalized = " ".join((content or "").split())[:500]
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def fuse(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        graph_results: Dict[str, Any],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        for doc in vector_results:
            candidates.append(
                {
                    "content": doc.get("content", ""),
                    "source": doc.get("metadata", {}).get("file_name", "vector_store"),
                    "type": "vector",
                    "score": float(doc.get("score", 0.0) or 0.0),
                    "metadata": doc.get("metadata", {}),
                }
            )

        for doc in bm25_results:
            candidates.append(
                {
                    "content": doc.get("content", ""),
                    "source": doc.get("metadata", {}).get("file_name", "bm25_store"),
                    "type": "bm25",
                    "score": float(doc.get("score", 0.0) or 0.0),
                    "metadata": doc.get("metadata", {}),
                }
            )

        for ctx in graph_results.get("related_contexts", [])[:10]:
            candidates.append(
                {
                    "content": "实体: " + str(ctx.get("name")) + "; 类型: " + str(ctx.get("type")) + "; 图谱距离: " + str(ctx.get("distance")),
                    "source": "knowledge_graph",
                    "type": "graph",
                    "score": 0.7 / max(float(ctx.get("distance", 1) or 1), 1.0),
                    "metadata": ctx,
                }
            )

        merged: Dict[str, Dict[str, Any]] = {}

        for item in candidates:
            content = item.get("content", "")
            if not content:
                continue

            key = self._fingerprint(content)
            source_type = item.get("type")
            base_score = float(item.get("score", 0.0) or 0.0)

            type_weight = {
                "vector": settings.VECTOR_WEIGHT,
                "bm25": settings.BM25_WEIGHT,
                "graph": settings.GRAPH_WEIGHT,
            }.get(source_type, 0.1)

            weighted_score = base_score * type_weight

            if key not in merged:
                item["fusion_score"] = weighted_score
                item["matched_by"] = [source_type]
                merged[key] = item
            else:
                merged[key]["fusion_score"] += weighted_score
                if source_type not in merged[key]["matched_by"]:
                    merged[key]["matched_by"].append(source_type)

        fused = sorted(
            merged.values(),
            key=lambda x: x.get("fusion_score", 0.0),
            reverse=True,
        )

        return fused[:top_k]

    def compress_context(self, evidences: List[Dict[str, Any]], max_chars: int = 6000) -> List[Dict[str, Any]]:
        compressed = []
        total = 0

        for evidence in evidences:
            content = evidence.get("content", "")
            if not content:
                continue

            remaining = max_chars - total
            if remaining <= 0:
                break

            if len(content) > remaining:
                content = content[:remaining]

            item = evidence.copy()
            item["content"] = content
            compressed.append(item)
            total += len(content)

        return compressed

evidence_fusion_service = EvidenceFusionService()
