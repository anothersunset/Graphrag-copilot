# GraphRAG Copilot

面向企业知识库的 Agentic GraphRAG。当前正式开发入口是 v3.x monorepo：

- API：`apps/api`（FastAPI + MCP）
- Web：`apps/web`（Next.js 15 + React 19）
- 核心包：`packages/*`
- 兼容代码：`legacy/backend` 与 `legacy/frontend`（legacy v1，不是默认入口）

目录总览与文件归类约定见 [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)，文档导航见 [docs/README.md](docs/README.md)。

## 环境要求

- Python 3.12+
- Node.js 22+
- uv
- pnpm 9.12.0（版本记录在根 `package.json`）

## 快速开始

安装根工作区依赖：

```bash
make install
```

分别启动 API 与 Web：

```bash
make api  # http://127.0.0.1:8000
make web  # http://127.0.0.1:3000
```

或在支持并行 make 的环境中运行：

```bash
make dev
```

`make api` 默认使用 `examples/demo_docs` 构建可查询的本地索引，因此启动后 readiness 与问答入口可直接验收。生产或自定义语料请覆盖：

```bash
GRAPHRAG_CORPUS_PATH=/path/to/corpus make api
```

## Docker 部署（v3 栈）

```bash
make docker-up     # 构建并启动 api(:8000) + web(:3000)，LLM 密钥从根 .env 读取
make docker-logs   # 跟踪日志
make docker-down   # 停止（保留数据卷）
```

- **API 容器**（`apps/api/Dockerfile`）：uv 多阶段构建、非 root 运行、自带 demo 语料，开箱即可问答；索引工件（`/data/index.json`）与运行历史（SQLite `/data/runs.db`）落在 `graphrag-v3_api-data` 卷上，**重启不重建索引、runs 可回查**。
- **Web 容器**（`apps/web/Dockerfile`）：pnpm 构建 + Next.js standalone 输出，经同源 `/api/graphrag/*` 代理访问 API（容器内 `http://api:8000`）。
- `.env` 不配 LLM 时自动降级为离线骨架模式，容器照常启动。
- 可选基础设施（Qdrant / Langfuse）见 `infra/docker/docker-compose.dev.yml`；v1 演示栈见 `make legacy-up`（与 v3 共用 8000/3000 端口，勿同时启动）。

## 检索栈真实化（可选接线）

默认部署只启用内存 KG 两路（PPR + 社区摘要），vector/BM25/reranker/LLM 全部关闭——`/readyz` 的 `dependencies.index.wiring` 会如实上报每个组件的状态。配置以下环境变量即可渐进接入真实栈：

| 组件 | 环境变量 | 说明 |
|---|---|---|
| LLM 生成 | `GRAPHRAG_LLM_BASE_URL` / `GRAPHRAG_LLM_API_KEY` / `GRAPHRAG_LLM_MODEL` | 三者齐备才启用（DeepSeek/智谱/vLLM 等 OpenAI 兼容端点）；启用后 `/v1/ask/stream` 为逐 token 真流式 |
| 向量检索 | `GRAPHRAG_QDRANT_URL` + `GRAPHRAG_EMBEDDING_MODEL` | 需先灌库；`GRAPHRAG_EMBEDDING_DIM` 默认 1024 |
| BM25 检索 | `GRAPHRAG_BM25_INDEX_PATH` | 指向 ingest 产出的 `bm25.pkl` |
| Rerank | `GRAPHRAG_RERANKER_MODEL` | 需安装 `graphrag-retrieval[rerank]`（FlagEmbedding） |
| KG 索引持久化 | `GRAPHRAG_INDEX_PATH` | 指向 ingest `--save-index` 产出的 `index.json`；存在则直接加载（LLM 级抽取重启不丢），不存在则从语料构建并回写 |
| Run 存储 | `GRAPHRAG_RUN_STORE_URL` | 默认 `memory://`；`sqlite:///data/runs.db` 跨进程/重启可查 `/v1/runs/{id}` |

灌库 CLI（细粒度分块 → KG → Qdrant 上插 → BM25 持久化，`--save-index` 持久化 KG 索引，可选 `--neo4j-uri` 导出图谱）：

```bash
make ingest ARGS="--corpus /path/to/corpus --out-dir data/index --save-index"
# 按产物启动，保证 KG/向量/BM25 服务同一份分块：
GRAPHRAG_INDEX_PATH=data/index/index.json \
GRAPHRAG_CORPUS_PATH=data/index/chunks.jsonl \
GRAPHRAG_BM25_INDEX_PATH=data/index/bm25.pkl \
GRAPHRAG_QDRANT_URL=http://localhost:6333 \
GRAPHRAG_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5 \
make api
```

## 正式 API 契约

- `GET /healthz`：进程存活
- `GET /readyz`：索引与依赖就绪
- `POST /v1/ask`：同步 GraphRAG 问答
- `POST /v1/ask/stream`：流式问答
- `GET /v1/runs/{run_id}`：读取一次运行及引用/审计轨迹
- `/v1/mcp`：MCP 挂载入口

运行 canonical smoke：

```bash
make smoke
# 或
BASE_URL=http://127.0.0.1:8000 uv run python scripts/smoke/api.py
```

如启用 API key，同时设置 `GRAPHRAG_API_KEY`。

## 前端配置

浏览器请求默认经由 `apps/web` 的同源 `/api/graphrag/*` 代理到 `http://127.0.0.1:8000`。服务端代理配置：

- `GRAPHRAG_API_URL`：上游 API 地址
- `GRAPHRAG_API_KEY`：可选上游 API key

legacy `legacy/frontend` 仍兼容 `NEXT_PUBLIC_API_BASE_URL`、`NEXT_PUBLIC_API_URL` 与 `NEXT_PUBLIC_API_BASE`，但不属于默认开发栈。

## 质量门与确定性评测

```bash
make test
make lint
make typecheck
pnpm build
uv run --package graphrag-eval python -m graphrag_eval.bench --strict
```

确定性评测覆盖 required answer points、Retrieval Recall@5、citation precision/recall/validity、Provenance Sufficiency 与 adversarial distractor 指标；不依赖 LLM、向量库或图数据库。

## 依赖与 CI

- JavaScript 工作区只使用根 `pnpm-lock.yaml`；CI 采用 frozen install。
- Python CI 固定 3.12，先运行根 Ruff/Pyright/全仓测试收集，再按实际包执行测试矩阵。
- workflow 模板位于 `infra/workflows-template`，修改后用 `make ci-activate` 同步到 `.github/workflows`。

## Docker 与 legacy

Docker 编排统一放在 `infra/docker/`：`docker-compose.dev.yml` 提供 v3.x 基础设施，`docker-compose.legacy.yml` 提供 v1 演示（`legacy/backend` + `legacy/frontend` + Neo4j）。legacy Web 仍使用根 pnpm 单锁。

从仓库根目录启动旧版演示：

```bash
cp .env.example .env  # 已有 .env 时保留现有配置
cp legacy/backend/.env.example legacy/backend/.env
make legacy-up
# 停止并保留数据卷：make legacy-down
```

旧路径 `backend/`、`frontend/`、`demo_docs/` 已分别迁入 `legacy/` 与 `examples/`；API 启动脚本为 `scripts/dev/start.sh`，HTTP 冒烟脚本为 `scripts/smoke/api.py`。本地覆盖率结果统一输出到 `artifacts/coverage/`。

迁移背景见：

- `docs/adr/0001-from-v1-to-v3.1.md`
- `docs/architecture/migration-roadmap.md`
- `docs/architecture/v3.1-final-spec.md`

## License

MIT
