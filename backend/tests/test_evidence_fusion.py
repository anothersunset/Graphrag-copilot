from app.services.evidence_fusion import EvidenceFusionService

def test_evidence_fusion_deduplicate_and_rank():
    service = EvidenceFusionService()
    vector_results = [
        {"content": "GraphRAG 使用知识图谱增强 RAG", "score": 0.9, "metadata": {"file_name": "a.md"}}
    ]
    bm25_results = [
        {"content": "GraphRAG 使用知识图谱增强 RAG", "score": 1.0, "metadata": {"file_name": "a.md"}}
    ]
    graph_results = {"related_contexts": [{"name": "GraphRAG", "type": "Technology", "distance": 1}]}

    fused = service.fuse(vector_results, bm25_results, graph_results)

    assert len(fused) >= 1
    assert "matched_by" in fused[0]
    assert fused[0]["fusion_score"] > 0
