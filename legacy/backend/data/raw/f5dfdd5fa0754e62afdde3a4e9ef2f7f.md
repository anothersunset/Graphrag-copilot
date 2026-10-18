# GraphRAG Copilot API 端点文档

## API 路由列表

所有端点以 /api 为前缀。

### 1. 文档管理
- POST /api/documents/upload - 文档上传，接收文件，解析、分块、向量化，后台执行实体抽取

### 2. 问答
- POST /api/query - 非流式问答，使用 LegacyOrchestrator.process_query 同步返回完整结果
- POST /api/query/stream - 流式问答 SSE 端点，使用 StreamingOrchestrator

### 3. 向量检索
- POST /api/vector/search - 向量搜索
- GET /api/vector/stats - 向量存储统计

### 4. 知识图谱
- GET /api/graph/stats - 图谱统计
- GET /api/graph/entity/{entity_name} - 实体查询
- GET /api/graph/path - 路径查找
- GET /api/graph - 全量图谱

### 5. 系统
- GET /api/system/status - 系统状态
- GET /health - 健康检查

## 文档上传完整流程

1. 用户上传文件到 /documents/upload
2. document_parser.parse 解析文件
3. chunk_text 分块（chunk_size=512, chunk_overlap=50）
4. embedding_service.embed 生成向量
5. vector_store.add_documents 存入 FAISS 向量库
6. bm25_store.add_documents 存入 BM25 索引
7. 后台 _extract_entities_background 执行实体抽取
8. kg_service.ingest_knowledge 写入 Neo4j
