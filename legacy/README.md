# Legacy v1 应用

`backend/` 与 `frontend/` 从仓库根目录迁入此处，保留源码、测试及已有数据和索引。
正式开发入口为根目录的 `apps/api`、`apps/web` 与 `packages/`。

在仓库根目录准备 `.env` 与 `legacy/backend/.env` 后运行 `make legacy-up`，
停止使用 `make legacy-down`。编排文件位于 `infra/docker/docker-compose.legacy.yml`。
前端仍是根 pnpm workspace 成员，不单独维护 lockfile。

本次目录迁移未解除旧版 API 对 `packages/graph` 的依赖。
历史知识库文档和持久化索引保留原内容，以维持 chunk ID 与评测 gold 映射。
