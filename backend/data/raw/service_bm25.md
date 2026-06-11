# service-bm25 模块文档

## 概述

`BM25Store` 是 GraphRAG Copilot 的 BM25 关键词检索服务，基于 `rank_bm25` 库的 `BM25Okapi` 算法实现，专为中文文档优化。模块位于 `backend/app/services/bm25_store.py`，通过单例 `bm25_store` 对外提供服务。

## 分词策略

`_tokenize(text)` 方法使用 `jieba.lcut(text)` 进行中文分词：

- 调用 jieba 的精确模式（lcut）
- 对分词结果进行 strip 和 lower 规范化
- 过滤掉空白 token

jieba 分词对中文文本的效果远优于简单的 `str.split()`，是 BM25 检索质量的关键。

## 添加文档

`add_documents(documents)` 方法：

1. 在线程锁（`threading.Lock`）保护下执行
2. 遍历文档列表，提取 `content` 字段
3. 对每条内容调用 `_tokenize()` 生成 token 列表
4. 追加到 `self.tokenized_corpus`
5. 用完整的 tokenized_corpus 重建 `BM25Okapi` 实例
6. 调用 `_save()` 持久化

注意：每次添加文档都会重建整个 BM25 索引，这是因为 `BM25Okapi` 不支持增量更新。

## 搜索

`search(query, top_k=10)` 方法：

1. 对查询文本进行 jieba 分词
2. 调用 `bm25.get_scores(query_tokens)` 获取每篇文档的 BM25 原始分数
3. 按分数降序排列，取前 `top_k` 条
4. 对每条结果进行 Sigmoid 归一化：

```python
normalized = 1.0 / (1.0 + 2.718 ** (-float(score) + 3.0))
```

Sigmoid 归一化的效果：score=0 映射到约 0.05，score=3 映射到 0.5，score=5 映射到约 0.88，score=10 映射到约 0.999。这避免了 BM25 原始分数（通常在 0~20+ 范围）直接暴露给融合层，同时保留了分数的相对排序。

## 持久化

存储目录为 `settings.VECTOR_DB_DIR`（默认 `data/vector_db/`）：

- `bm25.pkl`: pickle 序列化的 tokenized_corpus（`pickle.dump`）
- `bm25_documents.json`: 文档原始数据 JSON

启动时自动从磁盘恢复。若 `bm25.pkl` 或 `bm25_documents.json` 不存在，则跳过加载。加载失败时重置为空状态并记录日志。

## 统计信息

`get_stats()` 返回：

```python
{
    "type": "bm25",
    "total_documents": int,   # 文档总数
    "ready": bool,            # BM25 索引是否就绪
    "persisted": bool,        # 持久化文件是否存在
}
```

## 线程安全

所有写操作（`add_documents`）和持久化操作均在 `threading.Lock` 保护下执行，`_save()` 方法注释明确要求必须在锁内调用。搜索操作（`search`）为只读，无需加锁。
