from app.services.bm25_store import BM25Store

def test_bm25_search_keyword_match():
    store = BM25Store()
    docs = [
        {"content": "GraphRAG 使用知识图谱增强复杂关系检索。", "metadata": {"file_name": "graph.md"}},
        {"content": "普通 RAG 主要依赖向量相似度检索。", "metadata": {"file_name": "rag.md"}},
    ]

    store.add_documents(docs)
    results = store.search("知识图谱 GraphRAG", top_k=2)

    assert len(results) > 0
    assert "GraphRAG" in results[0]["content"]
    assert results[0]["score"] >= 0
