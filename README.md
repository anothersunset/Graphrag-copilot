# GraphRAG Copilot

面向企业知识库的 Agentic GraphRAG。当前正式开发入口是 v3.x monorepo：

- API：`apps/api`（FastAPI + MCP）
- Web：`apps/web`（Next.js 15 + React 19）
- 核心包：`packages/*`
- 兼容代码：`backend` 与 `frontend`（legacy v1，不是默认入口）

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

`make api` 默认使用 `demo_docs` 构建可查询的本地索引，因此启动后 readiness 与问答入口可直接验收。生产或自定义语料请覆盖：

```bash
GRAPHRAG_CORPUS_PATH=/path/to/corpus make api
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
BASE_URL=http://127.0.0.1:8000 uv run python test_api.py
```

如启用 API key，同时设置 `GRAPHRAG_API_KEY`。

## 前端配置

浏览器请求默认经由 `apps/web` 的同源 `/api/graphrag/*` 代理到 `http://127.0.0.1:8000`。服务端代理配置：

- `GRAPHRAG_API_URL`：上游 API 地址
- `GRAPHRAG_API_KEY`：可选上游 API key

legacy `frontend` 仍兼容 `NEXT_PUBLIC_API_BASE_URL`、`NEXT_PUBLIC_API_URL` 与 `NEXT_PUBLIC_API_BASE`，但不属于默认开发栈。

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

根 `docker-compose.yml` 仍用于 legacy v1 演示（`backend` + `frontend` + Neo4j）；legacy Web 已纳入根 pnpm 单锁。v3.x 基础设施依赖位于 `infra/docker/docker-compose.dev.yml`。

迁移背景见：

- `docs/adr/0001-from-v1-to-v3.1.md`
- `docs/architecture/migration-roadmap.md`
- `docs/architecture/v3.1-final-spec.md`

## License

MIT
