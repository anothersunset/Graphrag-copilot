# route-upload 模块文档

## 概述

`POST /api/documents/upload` 是 GraphRAG Copilot 的文档上传接口，实现了从文件接收、解析、分块、向量化到索引入库的完整流水线。路由定义位于 `backend/app/api/routes.py` 的 `upload_document` 函数。

## 请求规范

- **方法**: POST
- **路径**: `/api/documents/upload`
- **Content-Type**: `multipart/form-data`
- **参数**: `file`（UploadFile，必需）
- **认证**: `Depends(require_api_key)`（受 ENABLE_AUTH 控制）

## 处理流水线

### 1. 文件验证

`validate_upload_file(file)` 检查文件后缀是否在 `ALLOWED_EXTENSIONS` 集合中（.pdf, .docx, .pptx, .txt, .md, .jpg, .jpeg, .png, .mp3, .wav, .mp4）。不支持的格式返回 400。

读取文件内容后检查：
- 空文件返回 400（`"Uploaded file is empty"`）
- 超过 `settings.MAX_FILE_SIZE`（100MB）返回 413（`"Uploaded file is too large"`）

### 2. 文件存储

生成安全文件名：`uuid4().hex + suffix`（如 `a1b2c3d4...f5.pdf`），存储到 `settings.RAW_DIR` 目录。原始文件名保留在元数据中。

### 3. 文档解析

调用 `doc_parser.parse(file_path)` 进行多模态解析（PDF/DOCX/PPTX/图片OCR/音视频ASR），返回含 `file_hash`（SHA256）、`file_type`、`content.full_text` 的结构。解析失败返回 400。

### 4. 文本分块

调用 `doc_parser.chunk_text(full_text)`，使用 CHUNK_SIZE=512、CHUNK_OVERLAP=50 的滑动窗口切分。

### 5. 向量化与索引

- 调用 `embedding_service.embed(chunks)` 生成向量
- 构建文档元数据（file_name、stored_file_name、chunk_index、file_hash、source_type）
- 调用 `vector_store.add_documents(documents, embeddings)` 写入 FAISS 索引
- 调用 `bm25_store.add_documents(documents)` 写入 BM25 索引
- 索引失败返回 500

### 6. 后台实体抽取

通过 `background_tasks.add_task()` 异步执行 `_extract_entities_background()`：

- 调用 `llm_service.extract_entities(full_text[:3000])` 抽取实体和关系
- 调用 `kg_service.ingest_knowledge(entities, relations)` 批量写入 Neo4j
- 异常仅记录日志，不影响上传响应

## 响应结构

```python
class DocumentResponse:
    file_name: str           # 原始文件名
    file_type: str           # 文件类型（如 ".pdf"）
    content_length: int      # 全文字符数
    chunks_created: int      # 分块数量
    entities_extracted: int  # 固定为 0（后台异步）
    relations_extracted: int # 固定为 0（后台异步）
    document_hash: str       # SHA256 文件哈希
```

注意：`entities_extracted` 和 `relations_extracted` 在响应中固定为 0，因为实体抽取在后台异步执行，上传时无法获取结果。

## 错误处理

| 状态码 | 触发条件 |
|--------|----------|
| 400 | 不支持的文件格式、空文件、解析失败、解析内容为空 |
| 401 | API Key 无效（ENABLE_AUTH=true 时） |
| 413 | 文件超过 100MB |
| 500 | 向量/BM25 索引写入失败 |
