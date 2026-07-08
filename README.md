# GraphRAG Copilot

企业知识库场景下的 Agentic GraphRAG 项目。当前主分支处于 **v3.1 迁移期**：

- 默认开发栈：`apps/api` + `apps/web` + `packages/*`
- 兼容保留：`backend/` + `frontend/`（legacy v1）

## 当前推荐入口（v3.1）

### 1) 安装依赖

```bash
make install
```

### 2) 启动服务

```bash
make api   # http://localhost:8000
make web   # http://localhost:3000
```

也可以并行启动：

```bash
make dev
```

### 3) 健康检查

- API liveness: `GET /healthz`
- API readiness: `GET /readyz`

示例：

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

## 关键 API（v3.1）

- `POST /v1/ask`：主问答入口
- `POST /v1/mcp`：MCP server 挂载点（由 `apps/api` 提供）

项目内置 smoke 脚本会检查 `/healthz`、`/readyz` 与 `/v1/ask` 契约：

```bash
BASE_URL=http://localhost:8000 python test_api.py
```

## 前端 API 地址配置

前端默认回落到 `http://localhost:8000`。推荐使用：

- `NEXT_PUBLIC_API_BASE_URL`（首选）

当前也兼容：

- `NEXT_PUBLIC_API_BASE`
- `NEXT_PUBLIC_API_URL`

## Docker 与基础设施说明

### 根目录 `docker-compose.yml`

- 面向 legacy v1 的快速演示编排（`backend/` + `frontend/` + Neo4j）
- 如只做 v3.1 开发，不建议作为主入口

### `infra/docker/docker-compose.dev.yml`

- 面向 v3.1 的基础设施依赖（Qdrant / Neo4j / Langfuse）
- 用于本地联调检索、图谱与观测组件

## 常用命令

```bash
make test
make lint
make fmt
make typecheck
make ci-activate
```

`make ci-activate` 会把 `infra/workflows-template/*.yml.tmpl` 渲染到 `.github/workflows/`。

## 迁移状态

- 迁移决策：`docs/adr/0001-from-v1-to-v3.1.md`
- 路线图：`docs/architecture/migration-roadmap.md`
- v3.1 规格：`docs/architecture/v3.1-final-spec.md`

## Operational probes
- `/health` is the liveness probe and returns 200 when the API process is up.
- `/readyz` is the readiness probe and returns dependency details for vector, BM25, graph, embedding, and observability state.
- `test_api.py` is the local smoke runner. It checks liveness, readiness, system status, vector stats, graph stats, query, document upload, auth, and rate limiting.
- Frontend API base URL resolution order is `NEXT_PUBLIC_API_BASE_URL`, then `NEXT_PUBLIC_API_URL`, then `NEXT_PUBLIC_API_BASE`, then `http://localhost:8000`.

## License

MIT
