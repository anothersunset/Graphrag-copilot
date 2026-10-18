# config-all 配置参考文档

## 概述

GraphRAG Copilot 的全局配置通过 `pydantic_settings.BaseSettings` 管理，支持 `.env` 文件和环境变量覆盖。配置类位于 `backend/config/settings.py`，以单例 `settings` 对外暴露。

## 应用基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `APP_NAME` | str | `"GraphRAG Copilot"` | 应用名称 |
| `APP_VERSION` | str | `"1.0.0"` | 版本号 |
| `DEBUG` | bool | `False` | 调试模式 |
| `HOST` | str | `"0.0.0.0"` | 监听地址 |
| `PORT` | int | `8000` | 监听端口 |

## 目录结构

| 配置项 | 默认路径 | 说明 |
|--------|----------|------|
| `BASE_DIR` | `backend/` | 项目根目录 |
| `DATA_DIR` | `backend/data/` | 数据根目录 |
| `RAW_DIR` | `backend/data/raw/` | 原始上传文件目录 |
| `PROCESSED_DIR` | `backend/data/processed/` | 处理后文件目录 |
| `VECTOR_DB_DIR` | `backend/data/vector_db/` | 向量索引存储目录 |
| `GRAPH_DB_DIR` | `backend/data/graph_db/` | 图数据库目录 |

启动时自动创建所有目录（`mkdir(parents=True, exist_ok=True)`）。

## LLM 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `LLM_PROVIDER` | str | `"openai"` | LLM 提供商 |
| `LLM_MODEL` | str | `"glm-4-flash"` | 模型名称 |
| `LLM_API_KEY` | Optional[str] | `None` | API Key（从 .env 读取） |
| `LLM_BASE_URL` | Optional[str] | `None` | API Base URL |
| `LLM_TEMPERATURE` | float | `0.3` | 生成温度 |
| `LLM_MAX_TOKENS` | int | `4096` | 最大 token 数 |
| `ZHIPU_API_KEY` | Optional[str] | `None` | 智谱 API Key |
| `ZHIPU_BASE_URL` | str | `"https://open.bigmodel.cn/api/paas/v4"` | 智谱 API 地址 |

## Embedding 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `EMBEDDING_MODEL` | str | `"BAAI/bge-small-zh-v1.5"` | SentenceTransformer 模型 |
| `EMBEDDING_DIMENSION` | int | `512` | 向量维度 |
| `EMBEDDING_DEVICE` | str | `"cpu"` | 推理设备 |

## 检索配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `VECTOR_STORE_TYPE` | str | `"faiss"` | 向量存储类型 |
| `VECTOR_SEARCH_TOP_K` | int | `10` | 向量检索返回条数 |
| `BM25_TOP_K` | int | `10` | BM25 检索返回条数 |
| `CHUNK_SIZE` | int | `512` | 文本分块大小（字符） |
| `CHUNK_OVERLAP` | int | `50` | 分块重叠长度（字符） |
| `MAX_FILE_SIZE` | int | `104857600` (100MB) | 最大上传文件大小 |

## 融合权重

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `VECTOR_WEIGHT` | float | `0.55` | 向量检索权重 |
| `BM25_WEIGHT` | float | `0.15` | BM25 检索权重 |
| `GRAPH_WEIGHT` | float | `0.30` | 知识图谱权重 |
| `GRAPH_SEARCH_DEPTH` | int | `2` | 图遍历深度 |
| `VERIFICATION_THRESHOLD` | float | `0.8` | 答案验证置信度阈值 |

## Neo4j 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `NEO4J_URI` | str | `"bolt://localhost:7687"` | Bolt 连接地址 |
| `NEO4J_USER` | str | `"neo4j"` | 用户名 |
| `NEO4J_PASSWORD` | str | `"password"` | 密码 |

## 多模态配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `OCR_ENGINE` | str | `"paddleocr"` | OCR 引擎 |
| `ASR_MODEL` | str | `"base"` | Whisper ASR 模型 |
| `ASR_DEVICE` | str | `"cpu"` | ASR 推理设备 |

## 安全与限流

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `API_KEYS` | Optional[str] | `None` | 逗号分隔的允许 API Key 列表 |
| `ENABLE_AUTH` | bool | `False` | 是否启用认证（默认关闭） |
| `RATE_LIMIT_PER_MIN` | int | `60` | 每分钟请求限制 |
| `CORS_ORIGINS` | list[str] | `["http://localhost:3000", "http://localhost:5173"]` | CORS 允许源 |

## 日志配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `LOG_LEVEL` | str | `"INFO"` | 日志级别 |
| `LOG_DIR` | Optional[str] | `None` | 日志目录（默认 `data/logs/`） |

## 配置加载

配置从 `backend/.env` 文件加载（`env_file_encoding="utf-8"`），支持 `extra="allow"` 接受未声明的环境变量。所有敏感配置（API Key、密码）仅通过环境变量传入，仓库中不出现真实密钥。
