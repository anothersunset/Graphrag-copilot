# GraphRAG Copilot 系统架构文档

## 1. 技术栈总览

- **后端框架**: FastAPI 0.115 + Uvicorn
- **前端框架**: Next.js 16 + React 19 + Tailwind CSS 4
- **向量数据库**: FAISS (IndexFlatIP)
- **关键词检索**: jieba 分词 + rank-bm25 (BM25Okapi)
- **图数据库**: Neo4j 5.x + APOC 插件
- **嵌入模型**: BAAI/bge-small-zh-v1.5，维度 512，运行在 CPU
- **LLM 模型**: 默认使用智谱 GLM-4-Flash，支持通过环境变量配置其他 OpenAI 兼容模型（如 mimo-v2.5-pro）
- **OCR 引擎**: PaddleOCR
- **语音识别**: OpenAI Whisper
- **日志系统**: loguru，支持 DEBUG/INFO/WARNING/ERROR 级别，通过 LOG_LEVEL 环境变量控制

## 2. 系统分层

系统采用三层架构：展示层、应用层、数据层。

### 2.1 展示层（前端）
- Next.js 16 + React 19 + Tailwind CSS 4
- 文档上传界面、问答交互界面、知识图谱可视化
- 支持 SSE 流式输出

### 2.2 应用层（后端）
- FastAPI 提供 RESTful API
- Multi-Agent 编排器协调 5 个专业 Agent
- LangGraph 7 节点流水线（planner→retriever→evaluator→rewriter→generator→auditor→fallback）

### 2.3 数据层
- FAISS 向量存储（IndexFlatIP 内积索引）
- BM25 关键词索引（jieba + rank-bm25）
- Neo4j 知识图谱（APOC 插件支持高级查询）

## 3. 检索配置

- VECTOR_WEIGHT = 0.65（向量检索权重）
- BM25_WEIGHT = 0.15（关键词检索权重）
- GRAPH_WEIGHT = 0.20（图谱检索权重）
- VECTOR_SEARCH_TOP_K = 10
- BM25_TOP_K = 10
- GRAPH_SEARCH_DEPTH = 2
- VERIFICATION_THRESHOLD = 0.8

## 4. 文档处理配置

- CHUNK_SIZE = 512（分块大小）
- CHUNK_OVERLAP = 50（分块重叠）
- MAX_FILE_SIZE = 100MB (104857600 字节)

## 5. 安全配置

- API Key 鉴权: X-API-Key 请求头，通过 API_KEYS 环境变量配置，支持多个 Key 逗号分隔
- 限流: SlowAPIMiddleware，默认每分钟 60 次请求 (RATE_LIMIT_PER_MIN=60)
- CORS: 支持 localhost:3000 和 localhost:5173

## 6. 持久化机制

- FAISS 索引: faiss.index 文件 + documents.json 文档列表
- BM25 索引: bm25.pkl (pickle) + bm25_documents.json
- Neo4j: 图数据库独立持久化
- 文档原文: data/raw/ 目录
