"""Verify BM25Store persists its index and reloads it after restart.

以前 BM25 是纯内存索引，重启必须重新 fit。持久化修复后：
  - add_documents 后会写入 bm25.pkl + bm25_documents.json
  - 新实例初始化时会从磁盘重建 rank_bm25 索引和文档集
"""
from config.settings import settings


def test_bm25_persists_to_disk_and_reloads(tmp_path, monkeypatch):
    # 指向临时目录，避免污染真实数据库
    monkeypatch.setattr(settings, "VECTOR_DB_DIR", tmp_path)

    # 在 monkeypatch 之后才实例化新 store（模块级 bm25_store 单例在
    # import 时已用原 VECTOR_DB_DIR）
    from app.services.bm25_store import BM25Store

    docs = [
        {
            "id": "d1",
            "content": "GraphRAG 结合知识图谱与检索增强生成。",
            "metadata": {"file_name": "a.md"},
        },
        {
            "id": "d2",
            "content": "普通 RAG 依赖向量相似度检索。",
            "metadata": {"file_name": "b.md"},
        },
    ]

    store1 = BM25Store()
    store1.add_documents(docs)

    pkl_path = tmp_path / "bm25.pkl"
    docs_path = tmp_path / "bm25_documents.json"
    assert pkl_path.exists(), "add_documents 后应该写入 bm25.pkl"
    assert docs_path.exists(), "add_documents 后应该写入 bm25_documents.json"

    # 冷启动：新实例从磁盘 reload
    store2 = BM25Store()
    assert len(store2.documents) == 2, "新实例应从磁盘加载 2 篇文档"

    results = store2.search("知识图谱 GraphRAG", top_k=2)
    assert len(results) > 0, "冷启动后应能检索出原始文档"
    assert "GraphRAG" in results[0]["content"]
