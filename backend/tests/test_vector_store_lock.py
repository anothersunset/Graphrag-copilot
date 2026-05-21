"""Concurrency test for VectorStore.add_documents.

VectorStore.add_documents 使用 threading.Lock 保护 self.index.add + self.documents
追加 + _save 三个步骤。本用例模拟多线程同时写入，验证：
  1. 总计插入数量 == 线程数 * 每线程插入数
  2. index.ntotal 和 len(documents) 保持一致（无丟失 / 无越位）
如果 FAISS 未安装（本地环境缺少 faiss-cpu），该用例会被跳过。
"""
import threading

import pytest

from config.settings import settings


def test_concurrent_add_documents_does_not_lose_rows(tmp_path, monkeypatch):
    pytest.importorskip("faiss")

    monkeypatch.setattr(settings, "VECTOR_DB_DIR", tmp_path)

    # 在 monkeypatch 后才实例化，避免复用模块级 vector_store 单例
    from app.services.vector_store import VectorStore

    store = VectorStore()
    dim = store.dimension

    n_threads = 8
    per_thread = 5
    barrier = threading.Barrier(n_threads)
    errors = []

    def worker(tid: int):
        try:
            docs = [
                {"id": f"t{tid}-d{i}", "content": f"thread {tid} doc {i}",
                 "metadata": {"tid": tid}}
                for i in range(per_thread)
            ]
            # 各线程使用略不一样的 embedding 避免调优压缩
            embeddings = [
                [float((tid * 17 + i * 3 + k) % 7) / 7.0 for k in range(dim)]
                for i in range(per_thread)
            ]
            barrier.wait(timeout=10)  # 齐发写入，加大冲突概率
            store.add_documents(docs, embeddings)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"线程内报错: {errors}"

    expected = n_threads * per_thread
    assert store.index.ntotal == expected, \
        f"FAISS 索引数量 {store.index.ntotal} ≠ {expected}"
    assert len(store.documents) == expected, \
        f"文档数量 {len(store.documents)} ≠ {expected}"

    # 所有 id 必须唯一，证明没有出现覆盖写
    ids = {d["id"] for d in store.documents}
    assert len(ids) == expected
