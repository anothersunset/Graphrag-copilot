# service-vector 模块文档

## 概述

`VectorStore` 和 `EmbeddingService` 是 GraphRAG Copilot 的向量检索核心模块，分别负责向量索引管理和文本向量化。模块位于 `backend/app/services/vector_store.py`，通过单例 `vector_store` 和 `embedding_service` 对外提供服务。

## VectorStore 向量索引

### 索引类型

使用 FAISS 的 `IndexFlatIP`（内积索引），配合 L2 归一化后的向量实现余弦相似度检索。向量维度由 `settings.EMBEDDING_DIMENSION = 512` 决定。

### 添加文档

`add_documents(documents, embeddings)` 方法：

1. 将 embedding 列表转为 `numpy.float32` 数组
2. 调用 `faiss.normalize_L2` 进行 L2 归一化
3. 在线程锁保护下调用 `index.add()` 写入索引
4. 同步更新 `self.documents` 列表（含 id、content、metadata）
5. 调用 `_save()` 持久化

### 搜索

`search(query_embedding, top_k=None)` 方法：

1. 将查询向量转为 `numpy.float32` 并 L2 归一化
2. 调用 `index.search(query_array, min(top_k, ntotal))`
3. 返回含 `score`（内积 = 余弦相似度）和文档内容的结果列表
4. 默认 `top_k` 取 `settings.VECTOR_SEARCH_TOP_K = 10`

### 持久化

存储目录为 `settings.VECTOR_DB_DIR`（默认 `data/vector_db/`）：

- `faiss.index`: FAISS 索引二进制文件（`faiss.write_index`）
- `documents.json`: 文档元数据 JSON（`json.dump`，`ensure_ascii=False`）

启动时自动从磁盘恢复，加载失败则重建空索引。写入操作在 `threading.Lock` 保护下执行。

## EmbeddingService 文本向量化

### 模型加载

优先加载 `SentenceTransformer` 模型（`settings.EMBEDDING_MODEL`，默认 `BAAI/bge-small-zh-v1.5`），设备由 `settings.EMBEDDING_DEVICE` 指定（默认 `"cpu"`）。加载前设置 `HF_HUB_OFFLINE=1` 优先使用本地缓存。

若模型加载失败，降级为 `_hash_embed` 备选方案（基于 MD5 哈希的伪向量，维度 512）。

### embed() 方法

```python
def embed(self, texts: List[str]) -> List[List[float]]
```

- 使用 `model.encode(texts, normalize_embeddings=True)`
- 超过 10 条文本时显示进度条
- 返回归一化后的向量列表

### embed_query() 方法

```python
def embed_query(self, query: str) -> List[float]
```

单条查询的便捷方法，内部调用 `embed([query])[0]`。

### 哈希备选方案

`_hash_embed` 对每条文本取 `hashlib.md5` 的 digest（16 字节），转为 float32 后 tile 到 512 维，再 L2 归一化。该方案仅用于模型不可用时的降级，检索质量有限。
