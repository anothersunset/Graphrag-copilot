# 8 周渐进重构路线图 (W1 → W8)

> **执行模式**：AI = GitHub 侧负责人（代码 / commit / push / PR / Release / CI），User = 本地验证人（`git pull` + 本地跑 + 反馈 stdout/截图）
> **执行日志**：每日 Run Report 落地 Notion 主控页
> **配套文档**：[ADR-0001](../adr/0001-from-v1-to-v3.1.md) · [v3.1-final-spec.md](v3.1-final-spec.md)

## 总览

| 周 | 日期 | 主题 | 主要交付 | 验收指标 |
|---|---|---|---|---|
| **W1** | 05-21 → 05-27 | 骨架重构 + 迁移开场 | monorepo 布局 / ADR / 现代工具链 / Hero README | `make dev` 跑通 / pre-commit 全绿 / RAGAS baseline 测出 |
| **W2** | 05-28 → 06-03 | LangGraph 7 节点重写 | `apps/api/app/graph/` 替换 v1 orchestrator | 7 节点 trace 完整 / `pytest` 全过 / v1 demo 不退化 |
| **W3** | 06-04 → 06-10 | 四路检索 + Reranker | Qdrant 切换 + BGE-Reranker + Contextual Retrieval | Recall@5 ≥ 0.85 / 检索延迟 P95 ≤ 800ms |
| **W4** | 06-11 → 06-17 | Chunking 升级 + CRAG | Evaluator 节点 + 自纠错 + chunking 策略 A/B | CRAG 修复率 ≥ 70% / 幻觉率 ≤ 10% |
| **W5** | 06-18 → 06-24 | Langfuse + RAGAS + 原创指标 | 全链路 trace + RAGAS 报表 + Trace Completeness / Tool Call Necessity | Trace Completeness = 1.00 / 所有 RAGAS 指标 ≥ 红线 |
| **W6** | 06-25 → 07-01 | MCP + 前端 trace 可视化 | MCP server 暴露代码即工具 + React Flow 12 节点图 + 证据高亮 | MCP `tools/list` 通 / 前端可点节点看证据 |
| **W7** | 07-02 → 07-08 | DSPy + Auditor 闭环 | Auditor 节点 + DSPy 2.5 自调 prompt + Weekly Retro 复盘 | Tool Call Necessity ∈ [0.9, 1.1] / 审计覆盖率 = 1.00 |
| **W8** | 07-09 → 07-16 | Release + 简历叙事 | v1.0.0 Release + 90 秒 demo 视频 + 简历段 + 面试 FAQ | Release 发布 / coverage ≥ 70% / 90s demo 录制完 |

## 每周详细计划

### W1 · 骨架重构 + 迁移开场 (05-21 → 05-27)

| 日 | 主交付 | 验收 |
|---|---|---|
| **D1 (05-21 今天)** | ADR-0001 + v3.1 spec + roadmap + README banner + CHANGELOG + .editorconfig + docs/README | 6 篇文档 + 1 个 commit on main |
| **D2 (05-22)** | monorepo 骨架：`apps/api/` `apps/web/` `packages/` + Makefile + .pre-commit-config.yaml | `make help` 输出可读 |
| **D3 (05-23)** | Hello World：`apps/api/main.py` (FastAPI) + `apps/web/page.tsx` (Next.js 16) 都跑通 + `make dev` 一键启动 | 两端浏览器都能访问 |
| **D4 (05-24)** | pre-commit 全套：Ruff format + Pyright strict + Biome | `pre-commit run -a` 全绿 |
| **D5 (05-25)** | CI workflows：lint + type-check + pytest + frontend build + RAGAS baseline 评测 | GitHub Actions 全绿 + v1 baseline 数字落定 |
| **D6 (05-26)** | Hero README：项目定位 / 一句话 demo / 架构图 / quick start / 评测结果占位 | README 长度 ≥ 12KB |
| **D7 (05-27)** | ADR-0002（monorepo 容器与迁移截止线）+ W1 Weekly Retro | 2 篇文档 + Notion 主控页 §5 W1 Retro 写好 |

### W2 · LangGraph 7 节点重写 (05-28 → 06-03)

| 日 | 主交付 | 验收 |
|---|---|---|
| D1 | LangGraph 0.2.x state schema + 节点骨架（7 个空节点 + 路由）| `compile()` 成功 / 单元测试占位通 |
| D2 | Planner 节点：查询分解（DSPy + Instructor）| 多跳题分解 ≥ 2 子查询 |
| D3 | Retriever 节点：先复用 v1 三路检索（Qdrant 留 W3）| trace 显示 3 路并行 |
| D4 | Evaluator 节点骨架（CRAG 留 W4）| 阈值路由表完成 |
| D5 | Reasoner + Verifier + Generator + Auditor 骨架 | 端到端跑通 toy 题 |
| D6 | v1 单元测试迁入 + 适配新结构 | `pytest` 全过 |
| D7 | W2 Weekly Retro + v1 vs v2 性能对比表 | Notion 主控页 §5 W2 Retro |

### W3 · 四路检索 + Reranker (06-04 → 06-10)

| 日 | 主交付 | 验收 |
|---|---|---|
| D1 | Qdrant 1.12+ 接入 + docker-compose 加入 | Qdrant collection 创建成功 |
| D2 