# GraphRAG Copilot

<div align="center">

[![GitHub stars](https://img.shields.io/github/stars/anothersunset/Graphrag-copilot?style=flat-square)](https://github.com/anothersunset/Graphrag-copilot/stargazers)
[![GitHub license](https://img.shields.io/github/license/anothersunset/Graphrag-copilot?style=flat-square)](https://github.com/anothersunset/Graphrag-copilot/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat-square&logo=next.js)](https://nextjs.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)
[![CI](https://img.shields.io/github/actions/workflow/status/anothersunset/Graphrag-copilot/ci.yml?style=flat-square&label=CI)](https://github.com/anothersunset/Graphrag-copilot/actions)
[![Release](https://img.shields.io/github/v/release/anothersunset/Graphrag-copilot?style=flat-square)](https://github.com/anothersunset/Graphrag-copilot/releases)

</div>

> 🚧 **v3.1 重构进行中** (2026-05-21 → 2026-07-16) — 本项目正在通过 **8 周渐进重构** 从 v1（已可跑 demo）升级到 v3.1（LangGraph 7 节点 Agentic RAG + 四路检索 + CRAG + Langfuse trace + RAGAS 评测 + MCP server）。当前 main 同时包含 v1 实现（`backend/` + `frontend/`）与 v3.1 重构骨架（`apps/`，建设中）。完整迁移决策见 **[ADR-0001](docs/adr/0001-from-v1-to-v3.1.md)**，8 周路线图见 **[migration-roadmap.md](docs/architecture/migration-roadmap.md)**，v3.1 完整技术规格见 **[v3.1-final-spec.md](docs/architecture/v3.1-final-spec.md)**。

> 面向企业知识库的多模态 GraphRAG + Multi-Agent 检索增强生成系统

## 核心特性
- 多模态文档解析：PDF / DOCX / PPTX / 图片 OCR / 音视频 ASR
- 混合检索：FAISS 向量 + BM25 关键词 + Neo4j 知识图谱
- Multi-Agent 编排：查询理解 -> 检索 -> 推理 -> 验证 -> 生成
- 可解释 & 抗幻觉：附带来源引用、置信度、推理路径
- 优雅降级：Neo4j / LLM / Embedding 单点故障不会拖垮系统
- 工程化完备：Docker Compose、pytest、eval 脚本、前端演示闭环
- 安全与可观测：可选 API Key 鉴权、统一 loguru 日志、限流中间件

## 技术栈
- 后端：Python 3.11+ / FastAPI 0.115 / Uvicorn
- LLM：智谱 GLM-4-Flash（OpenAI 兼容 SDK）
- 向量库：FAISS (IndexFlatIP)
- 图数据库：Neo4j 5.x (APOC)
- 嵌入：BAAI/bge-small-zh-v1.5 (dim 512)
- 检索：jieba + rank-bm25
- 前端：Next.js 16 / React 19 / Tailwind CSS 4
- 容器：Docker + Docker Compose

## 快速启动（本地）
```

cd backend

cp .env.example .env   # 填入 ZHIPU_API_KEY

pip install -r requirements.txt

uvicorn main:app --reload --port 8000

```

## 快速启动（Docker）
```

cp backend/.env.example backend/.env

docker-compose up -d

```

## 测试
项目同时维护三类测试：**单元测试**（pytest，不依赖外部服务）、**冷烟脚本**（test_api.py，针对已启动服务走一遭关键接口）、**评测脚本**（eval/run_eval.py，度量问答质量）。

### 单元测试
```

cd backend && pytest -q

```
关键用例覆盖：
- `tests/test_security.py` — X-API-Key 鉴权 × 4 + slowapi 限流 429
- `tests/test_bm25_persistence.py` — BM25 索引写盘 + 冷启动重加载
- `tests/test_kg_batch.py` — KG 入图 `UNWIND` 分组批处理（mock Neo4j）
- `tests/test_vector_store_lock.py` — FAISS 多线程并发写入不丢数
- `tests/test_vector_store.py` / `test_routes.py` / `test_orchestrator*.py` / `test_evidence_fusion.py` / `test_fallback.py` / `test_llm_service.py` / `test_bm25_store.py`

### 冷烟脚本（smoke）
服务启动后运行，未通过会以非 0 退出，可作为部署/发布闸门：
```

BASE_URL=http://localhost:8000 python test_api.py

# 启用鉴权 + 限流验证（API_KEY 需与服务端 API_KEYS 中某一个一致）
BASE_URL=http://localhost:8000 \
API_KEY=your-key \
ENABLE_AUTH=true \
RATE_LIMIT_PER_MIN=5 \
python test_api.py

```
覆盖 9 个检查点：健康检查、系统状态、向量/图谱统计、问答、文档上传、鉴权(缺头·正确头)、限流 429。

### 评测脚本
```

python eval/run_eval.py

```

## API
启动后访问 http://localhost:8000/docs 。

## 安全配置
GraphRAG Copilot 默认允许本地匿名访问，便于快速试用；在生产、公网或多租户环境中请启用鉴权与限流。
- `ENABLE_AUTH=true` 后，写入、问答、流式接口均需要请求头 `X-API-Key`。
- `API_KEYS` 采用逗号分隔多个可吊销 key，仅有服务端启动时读取的 key 才会被接受。
- `RATE_LIMIT_PER_MIN` 控制单 IP 问答限流，默认 60。该限流由 `SlowAPIMiddleware` 全局生效。
- `.env` 已在 `.gitignore` 中被忽略；仓库中仅提供 `.env.example` 占位值，请勿将真实密钥提交入库。
- 在 `/api/system/status` 中可查看当前鉴权状态与限流阈值。

## 已知限制与演进路线
项目当前作为面试作品集原型，以下是已识别的短板，请按优先级阅读：

### 性能 / 可扩展性
- BM25 仅在内存构建，重启会丢失。本仓已增加 pickle 持久化（`backend/data/vector_db/bm25.pkl`），后续版本考虑接入 Whoosh / Elasticsearch 以支持增量更新。
- FAISS 默认使用 `IndexFlatIP` 是 O(n) 扫描，适合千级向量；如果扩到百万级，请切换到 `IndexIVFFlat` / `HNSW`。
- KG 写入已优化为 `UNWIND` 批量 MERGE，后续可考虑采用 APOC `apoc.periodic.iterate` 进一步并发。

### 检索 / 推理质量
- 实体抽取仅处理文档前 3000 字符，后续需要分段抽取 + 同义词联通，避免同名实体在图中被重复创建。
- Verification 仅做文本抽查，后续会接入 LLM-as-judge 与 Citation Recall 评价。
- Eval 仅含 5 道题，后续会扩充多跳 / 干扰 / 负例集，并补充 hit@k / faithfulness 指标。

### 安全 / 合规
- API Key + 限流仅为最小可用方案，生产部署建议在网关层增加 OAuth / mTLS / SSO。
- 当前未区分租户与文档权限，后续需与 RBAC / ACL 集成。
- 上传仅做扩展名与大小检查，生产环境请增加 MIME 检查、病毒扫描、上传颁发限额。

### 可观测 / 运维
- 日志已由 print 迁移到 loguru，后续会接入 OpenTelemetry / Prometheus exporter 以采集检索延迟、LLM token 消耗、失败率。
- 现阶段未接入告警，后续会与 Grafana / 钉钉 / Slack webhook 集成。

### 前端 / 交互
- 前端 API 地址默认 `http://localhost:8000`，生产环境请使用 `NEXT_PUBLIC_API_BASE_URL` 覆盖。
- 问答交互尚未支持多轮上下文会话，后续会接入会话存储与收发上下文压缩。

## License
MIT
