# 📋 待办与交接清单（Backlog）

> 整理于 2026-09-23，基于：4 篇 devlog、`docs/eval-report.md`、git 历史、
> 双线深度分析（代码/架构 + 进度/dev 记录），以及 2026-09-23 已完成的
> 「检索栈真实化」第一阶段工作。每项标注优先级、证据位置与验收标准。
> 完成一项就把它移到文末「已完成」区并注明日期。

---

## 当前状态快照

- **分支**：`codex/p0-p1-repair`，领先 `origin/main` 10 个提交（未推送），
  另有 2026-09-23「检索栈真实化」改动**未提交**（工作区）。
- **质量门（2026-09-23 实测全绿）**：pytest 235 通过 / 覆盖率 83%；
  ruff、pyright 0 错误；`graphrag_eval.bench --strict` 全 KPI 通过；
  前端 biome + tsc 通过。
- **路线图位置**：约 W6~W7（`docs/architecture/migration-roadmap.md`），
  W8 发布项未启动。

---

## P0 — 阻塞基线，最先处理

> 2026-09-23：P0 两项已完成，详见文末「已完成」区。P1 顺位上移。

---

## P1 — 影响核心质量

### 3. PPR 分数归一化或接 BGE reranker，让 KG 路真正参与 CRAG 路由
- **问题**：PPR 原始分 ~1e-3，低于 CRAG 阈值（use=0.5），
  KG-only local 查询会误走 fallback。
- **证据**：`docs/devlog-2026-07-08-graphrag-index-layer.md` §4。
- **起点文件**：`packages/kg/src/graphrag_kg/pagerank.py`、
  `packages/graph/src/graphrag_graph/crag.py`、
  `packages/graph/src/graphrag_graph/nodes/evaluator.py`。
- **验收**：构造 KG-only 命中的用例，CRAG 决策为 `use` 而非 `fallback`；
  对应单测入 `packages/graph/tests/`。

### 4. 检索栈真实化第二阶段
- **内容**（第一阶段遗留，见 `apps/api/src/graphrag_api/ingest.py` 模块注释）：
  - KG 索引持久化：目前 API 启动时用 `load_corpus` 原地重建（离线质量），
    ingest 时的 LLM 级抽取/社区摘要不能在重启后存活。
    方向：`GraphRAGIndex` 序列化（networkx graph + communities + chunk_texts），
    API 启动时优先加载已持久化索引。
  - 真实环境端到端验证：Qdrant 容器（`infra/docker/docker-compose.dev.yml`）
    + 真实 embedding 模型跑一次 `make ingest` + `make api` + smoke，
    确认 `/readyz` wiring 上报 `VectorRetriever`、答案引用来自 vector 路。
  - LLM 抽取/摘要质量评测：`build_index(llm=...)` 打开 gleaning 抽取后，
    在真实语料上对比 co-occurrence 基线（devlog-07-08 明确提出未验证）。
- **验收**：重启后 KG 不退化；端到端 smoke 日志可见四路融合。

### 5. 复核 boundary refusal 指标口径
- **问题**：Boundary Refusal Rate 从早期口径 0.8333 掉到最终评测 0.08，
  且 `46b50e4` 用了 "relaxed post-check"，疑似口径漂移而非真实回退。
- **证据**：`docs/devlog-2026-06-11-benchmark-evaluation.md` §4。
- **验收**：明确口径定义并固定进 `packages/eval`；如属实回退则修复。

---

## P2 — 评测体系与发布兑现

### 6. 人工抽检 + 外部数据集对标
- `docs/eval-report.md` §6.5/§7.1/§7.2：人工抽检（10~20 题、Cohen's kappa）
  未执行；MultiHop-RAG / HotpotQA 等外部集对标全空。
- 顺带：crossdoc 仍是短板题型（最高 ~0.69），可在抽检中重点覆盖。

### 7. 兑现 W5 / W8 收尾项
- Langfuse trace 下钻接通：`packages/observability`（`langfuse_tracer.py`
  当前 40% 覆盖）与 dev compose 里的 Langfuse 服务实际未串进主链路验证。
- 覆盖率门槛：`pyproject.toml` 中 `fail_under = 0`，实测已 83%，
  应提到 70 兑现 spec 承诺（防止回退）。
- 打 v3 正式 release（CHANGELOG + tag；`release-please` 配置已就绪）。

### 8. SSE 真流式
- `apps/api/src/graphrag_api/app.py` 的 `event_stream` 是伪流式：
  `execute()` 完整返回后才发 token。与前端 `askStream()` 的叙事不匹配。
- 方向：generator 节点透传 LLM token 流（LangGraph `astream_events`）。

---

## P3 — 工程债与清理

| 项 | 说明 | 位置 |
|---|---|---|
| RunStore 单进程内存 | 多 worker 下 `GET /v1/runs/{id}` 必 404；方向：Redis/SQLite 后端 + `run_store` 接口化 | `apps/api/src/graphrag_api/run_store.py` |
| schemas 重复定义 | `CRAGBranch`/`CRAGDecision` 双份；API 层 `RetrievalTraceExporter` 手拼 dict 未消费 `schemas.RetrievalTrace` | `packages/schemas/src/graphrag_schemas/{crag,retrieval_trace}.py` |
| 文档漂移 | `PROJECT_STRUCTURE.md` 描述的 routes/ 目录、7 包数量与实际不符 | 根目录 |
| 空壳包 | `packages/reranker`、`packages/retriever` 只有 `__init__.py`，易误导 | 对应目录 |
| dependabot 分支堆 | 远端 14 个分支待处置（合并或关闭） | origin |
| v1 legacy 归档 | ADR-0001 约定的时间表未执行；注意 `backend/app/agents/orchestrator.py` 已反向依赖 v3 `packages/graph`，归档时需解耦 | `backend/`、`frontend/` |
| 敏感默认值 | v1 compose 硬编码 `neo4j/graphrag123`；langfuse NextAuth secret 默认值 | `docker-compose.yml`、`infra/docker/` |
| planner 启发式泛化 | 中文关键词表硬编码，跨语言/领域弱；可评估用已接线的 LLM 兜底路径替代 | `packages/graph/src/graphrag_graph/nodes/planner.py` |

---

## 环境 & 运行速查（新接手者）

```bash
make install        # uv sync --all-packages --dev + pnpm install --frozen-lockfile
make api            # FastAPI :8000（默认 demo_docs，离线即可用）
make web            # Next.js :3000
make smoke          # /healthz /readyz /v1/ask 契约验收
make test && make lint && make typecheck
uv run --package graphrag-eval python -m graphrag_eval.bench --strict
make ingest ARGS="--corpus demo_docs --out-dir data/index --skip-qdrant"  # 灌库（离线模式）
```

- 检索栈接线环境变量表：根 `README.md`「检索栈真实化」一节。
- 本地启动配置参考 `.claude/launch.json`（v1 :8000/:3000，v3 :8001/:3001）。
- 跑真实 LLM 评测前确认 DeepSeek key（已从 mimo 迁移，限流监控先开，
  见 devlog-06-11 §2.13 的教训）。

---

## 已完成（归档区）

- [x] 2026-09-23 **P0-1 分支处置**：「检索栈真实化」整理为 commit
  `36511a8` 并 fast-forward 合入本地 `main`；合并后 main 上
  pytest 235 通过 / 83% 覆盖、ruff + pyright 0 错、bench strict 全绿、
  biome + tsc 通过（推送远端仍待负责人确认）。
- [x] 2026-09-23 **P0-2 gold ID 映射修复**：三层断链（入库无稳定
  chunk_id / 客户端读错字段 / gold 语义 ID 无映射）全部修复；
  34 个语义 ID 映射经人工通读 60 chunks 标注并有完整性单测守护；
  50 题离线重跑 Recall@5 = 0.4716（修复前恒 0），45/50 题 > 0；
  新基线 `eval/results/real_eval_baseline_offline_2026-09-23.json`，
  历史结果文件未动。详见 `docs/eval-report.md` §6.0.0。
- [x] 2026-09-23 检索栈真实化第一阶段：可选接线 + 灌库 CLI +
  `/readyz` 如实上报（本文件「当前状态快照」所述质量门全绿）。
- [x] 2026-07-09 合并核实与 2 处静默 bug 修复（devlog-2026-07-09）。
- [x] 2026-07-08 GraphRAG 索引层（gleaning/消歧/Louvain/PPR）。
- [x] 2026-06-11 50 题 benchmark 评测体系 + 13 项 P0/P1 修复。
- [x] 2026-05-22 v3.2 monorepo CI 修复 + 哨兵测试。
