# 8 周渐进重构路线图 (W1 → W8)

> **执行模式**：AI = GitHub 侧负责人（代码 / commit / push / PR / Release / CI），User = 本地验证人（`git pull` + 本地跑 + 反馈 stdout/截图）
> **执行日志**：每日 Run Report 落地 Notion 主控页。
> **配套文档**：[ADR-0001](../adr/0001-from-v1-to-v3.1.md) · [v3.1-final-spec.md](v3.1-final-spec.md)

## 总览

| 周 | 日期 | 主题 | 主要交付 | 验收指标 |
|---|---|---|---|---|
| **W1** | 05-21 → 05-27 | 骨架重构 + 迁移开场 | monorepo 布局 / ADR / 现代工具链 / Hero README / v1 baseline | `make dev` 跑通 · pre-commit 全绿 · RAGAS baseline 测出 |
| **W2** | 05-28 → 06-03 | LangGraph 7 节点重写 | `apps/api/app/graph/` 替换 v1 orchestrator | 7 节点 trace 完整 · `pytest` 全过 · v1 demo 不退化 |
| **W3** | 06-04 → 06-10 | 四路检索 + Reranker | Qdrant 切换 + BGE-Reranker-v2-m3 + Contextual Retrieval | Recall@5 ≥ 0.85 · 检索延迟 P95 ≤ 800ms |
| **W4** | 06-11 → 06-17 | Chunking 升级 + CRAG | Evaluator 节点 + 自纠错路径 + chunking 策略 A/B | CRAG 修复率 ≥ 70% · 幻觉率 ≤ 10% |
| **W5** | 06-18 → 06-24 | Langfuse + RAGAS + 原创指标 | 全链路 trace + RAGAS 报表 + Trace Completeness + Tool Call Necessity | Trace Completeness = 1.00 · 所有 RAGAS 指标 ≥ 红线 |
| **W6** | 06-25 → 07-01 | MCP + 前端 trace 可视化 | MCP server 暴露代码即工具 + React Flow 12 节点图 + 证据高亮 | MCP `tools/list` 通 · 前端可点节点看证据 |
| **W7** | 07-02 → 07-08 | DSPy + Auditor 闭环 | Auditor 节点 + DSPy 2.5 自调 prompt + Weekly Retro 复盘 | Tool Call Necessity ∈ [0.9, 1.1] · 审计覆盖率 = 1.00 |
| **W8** | 07-09 → 07-16 | Release + 简历叙事 | v1.0.0 Release + 90 秒 demo 视频 + 简历段 + 面试 FAQ | Release 发布 · coverage ≥ 70% · 90s demo 录制完 |

## W1 · 骨架重构 + 迁移开场 (05-21 → 05-27)

| 日 | 主交付 | 验收 |
|---|---|---|
| **D1 (05-21 今天)** | ADR-0001 + v3.1 spec + roadmap + README banner + CHANGELOG + .editorconfig + docs/README → 1 个 commit on main | 7 篇新增/更新文档 · main 仗可见 ADR 链接 |
| **D2 (05-22)** | monorepo 骨架：`apps/api/` `apps/web/` `packages/` + `Makefile` + `.pre-commit-config.yaml` + `CONTRIBUTING.md` | `make help` 输出可读 · 目录结构与 ADR-0001 Migration Boundary 表一致 |
| **D3 (05-23)** | Hello World：`apps/api/main.py` (FastAPI) + `apps/web/page.tsx` (Next.js 16) 跑通 + `make dev` 一键启动 | 两端浏览器都能访问 · v1 `backend/`+`frontend/` 不退化 |
| **D4 (05-24)** | pre-commit 全套：Ruff format + Pyright strict + Biome + markdownlint | `pre-commit run -a` 全绿 |
| **D5 (05-25)** | CI workflows：lint + type-check + pytest + frontend build + **v1 baseline RAGAS 评测** | GitHub Actions 全绿 · v1 baseline 数字落定（Faithfulness / Context Precision / Recall@5） |
| **D6 (05-26)** | Hero README：项目定位 / 一句话 demo / 架构图 / quick start / 评测结果占位 | README 长度 ≥ 12KB · markdownlint 通 |
| **D7 (05-27)** | ADR-0002（monorepo 容器与迁移截止线）+ W1 Weekly Retro | 2 篇文档 · Notion 主控页 W1 Retro 写好 |

## W2 · LangGraph 7 节点重写 (05-28 → 06-03)

| 日 | 主交付 | 验收 |
|---|---|---|
| D1 | LangGraph 0.2.x state schema + 节点骨架（7 个空节点 + 路由）| `compile()` 成功 · 单元测试占位通 |
| D2 | Planner 节点：查询分解（DSPy + Instructor）| 多跳题分解 ≥ 2 子查询 |
| D3 | Retriever 节点：先复用 v1 三路检索（Qdrant 留 W3）| trace 显示 3 路并行 |
| D4 | Evaluator 节点骨架（CRAG 留 W4）| 阈值路由表完成 |
| D5 | Reasoner + Verifier + Generator + Auditor 骨架 | 端到端跑通 toy 题 |
| D6 | v1 单元测试迁入 + 适配新结构 | `pytest` 全过 |
| D7 | W2 Weekly Retro + v1 vs v2 性能对比表 | Notion 主控页 W2 Retro |

## W3 — W8 · 周度概要

> W3-W8 的每日明细计划在**每周周一开工时生成**，以便吸收上一周 Retro 的发现（agile 实践）。以下是周级关键项。

### W3 · 四路检索 + Reranker
- Qdrant 1.12+ 接入（docker-compose 加入 Qdrant collection）
- bge-large-zh-v1.5 升级与重建索引（512 → 1024 维）
- v1 FAISS 接口层透明切换到 Qdrant（单测不改）
- BGE-Reranker-v2-m3 二次精排（人工/自动 NDCG 对比）
- Contextual Retrieval（Anthropic）：chunk 前置摘要
- 四路检索加权调参 → Recall@5 ≥ 0.85
- W3 Weekly Retro

### W4 · Chunking 升级 + CRAG
- Chunking 策略 A/B：fixed / semantic / sliding window
- Evaluator 节点置信度评分（LLM-as-judge + retrieval score）
- CRAG rewrite 路径（0.3-0.7 跳查询改写，上限 2 次）
- CRAG fallback 路径（< 0.3 跳 web search / 拒答）
- CRAG 修复率 ≥ 70%、幻觉率 ≤ 10%
- ADR-0003（CRAG 阈值最终值）+ W4 Weekly Retro

### W5 · Langfuse + RAGAS + 原创指标
- Langfuse 2.x self-hosted（docker-compose 加入）
- LangGraph 7 节点接 Langfuse trace decorator
- RAGAS 0.2+ 集成：Faithfulness / Context Precision / Answer Relevancy / Context Recall / Context Entity Recall
- DeepEval 2.x 集成 + 自定义幻觉测试
- 原创指标：Trace Completeness = 1.00、Tool Call Necessity 计算可用
- W5 Weekly Retro + 完整指标表板

### W6 · MCP + 前端 trace 可视化
- MCP SDK 1.x 接入 + 暴露 ≥ 3 个工具：`query` / `retrieve` / `kg_path`
- MCP server 跨工具调用测试（从外部 client）
- 前端 React Flow 12 节点图 + 实时流式（Vercel AI SDK 5 SSE）
- 证据高亮：点节点 → 显示该节点检索/推理的证据
- shadcn/ui 重做 4 个页面 + W6 Weekly Retro

### W7 · DSPy + Auditor 闭环
- DSPy 2.5.x signature 定义 + `dspy compile` 成功
- Auditor 节点：工具调用必要性评估
- BootstrapFewShot 优化 Auditor prompt（优化前后对比）
- 审计覆盖率 = 1.00（所有请求强制经 Auditor）
- Auditor 反馈闭环：失败 case 自动入库
- DSPy 自动调 Planner / Verifier prompt + W7 Weekly Retro

### W8 · Release + 简历叙事
- release-please 接入 + Conventional Commits 整理 → CHANGELOG 自动生成
- e2e 测试 + coverage ≥ 70%
- Docker multi-stage build 优化 · API 镜像 ≤ 800MB
- 90 秒 demo 视频脚本 + 录制
- 简历段 + 项目 1-pager + 面试 FAQ 7 问
- **v1.0.0 Release 发布**（需 Notion @ 批准）+ 整体 Retro

## 验证日历（v1 baseline → v3.1 final）

| 周 | 当周新增度量 |
|---|---|
| W1 D5 | **v1 baseline** 跑 RAGAS（旧 5 题 + 新 50 题）记录 Faithfulness / Context Precision / Recall@5 |
| W3 D7 | 检索质量首次冲指标线（Recall@5 ≥ 0.85） |
| W4 D7 | CRAG 修复率 ≥ 70% + 幻觉率 ≤ 10% |
| W5 D7 | 完整指标墙（10 个指标全部上线） |
| W7 D7 | Tool Call Necessity ∈ [0.9, 1.1] / 审计覆盖率 = 1.00 |
| W8 D2 | Test coverage ≥ 70% |

## 风险与降级

如果某周指标未达标：
- **偏离 ≤ 5%**：本周内调参补救，不延期
- **5–15% 偏离**：触发 ADR 决策（要么妥协指标，要么延期 ≤ 1 周）
- **> 15% 偏离**：Weekly Retro 中重新评估范围，可能砍掉次要功能（如 W7 DSPy 优化或 W6 React Flow 可点交互）以保核心指标

## 变更管理

- 任何偏离 [v3.1-final-spec.md](v3.1-final-spec.md) 锁定项的决策须撰写 ADR
- 任何高风险操作（见 spec §5 安全护栏）须 Notion 主控页 @ 项目作者获得显式批准
- 任何范围变更（加项 / 减项 / 延期）须在下一个 Weekly Retro 中明示

---
*8 周路线图由 @anothersunset 与 Notion AI 协作锁定于 2026-05-21（W1 D1）。任何延期 / 范围变更须通过 ADR 决策。*
