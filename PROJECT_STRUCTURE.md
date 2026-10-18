# GraphRAG Copilot — 项目结构（当前快照）

> 本文件描述当前工作区的真实代码布局，与代码同步维护。v1 单体与 v3.x monorepo 双轨并存，v3.x 是默认开发入口。
>
> 迁移决策见 [`docs/adr/0001-from-v1-to-v3.1.md`](docs/adr/0001-from-v1-to-v3.1.md)、[`docs/adr/0002-monorepo-container.md`](docs/adr/0002-monorepo-container.md)；8 周路线图见 [`docs/architecture/migration-roadmap.md`](docs/architecture/migration-roadmap.md)；待办清单见 [`docs/backlog.md`](docs/backlog.md)。

## 顶层布局

```text
Graphrag-copilot/
├── apps/                            # 正式应用
│   ├── api/                         # FastAPI + MCP；src/ 与 tests/ 同包管理
│   └── web/                         # Next.js Web
├── packages/                        # 7 个共享 Python 包，各自保留 src/ 与 tests/
│   ├── schemas/
│   ├── retrieval/
│   ├── parsers/
│   ├── kg/
│   ├── graph/
│   ├── observability/
│   └── eval/                        # 确定性评测库与 bench CLI
├── legacy/                          # 兼容演示应用，与正式应用隔离
│   ├── backend/                     # v1 API、测试、配置及原有数据/索引
│   └── frontend/                    # v1 Web，仍使用根 pnpm 单锁
├── examples/
│   └── demo_docs/                   # make api 默认演示语料
├── eval/                            # 服务评测脚手架、datasets/、prompts/、tests/、results/
├── integrations/
│   └── notion/                      # 外部同步数据快照及接入说明
├── docs/
│   ├── adr/                         # 架构决策
│   ├── architecture/                # 技术规格、迁移路线与发布流程
│   ├── development/                 # 历史开发记录
│   ├── evaluation/                  # 评测报告
│   ├── backlog.md                   # 待办与交接
│   └── README.md                    # 文档导航
├── infra/
│   ├── docker/                      # dev 与 legacy Docker Compose
│   └── workflows-template/          # GitHub Actions 模板
├── scripts/
│   ├── dev/start.sh                 # 从任意工作目录启动正式 API
│   ├── smoke/api.py                 # 正式 API 的 HTTP 冒烟检查
│   └── install-workflows.sh         # 渲染模板到 .github/workflows/
├── artifacts/coverage/              # 本地覆盖率产物，不入库
├── .github/                         # 工作流、依赖更新与协作配置
├── Makefile                         # 安装、开发、质量门、legacy 编排统一入口
├── pyproject.toml / uv.lock         # Python workspace 与依赖锁
├── package.json / pnpm-*.yaml       # JavaScript workspace、脚本与依赖锁
├── .env.example                     # 根环境变量示例
├── README.md / PROJECT_STRUCTURE.md # 项目入口与结构说明
└── CONTRIBUTING.md / CHANGELOG.md / LICENSE
```

## 文件归类约定

- 应用代码放 `apps/<app>/src/`，共享能力放 `packages/<package>/src/`；单元测试随应用或包放在 `tests/`，保留现有导入边界。
- v1 应用及其运行数据放 `legacy/`；本次仅搬迁目录，仍保留对共享包的依赖。
- 跨服务评测材料放 `eval/`；可重复分发的演示输入放 `examples/`。
- 自动化脚本放 `scripts/`，部署配置放 `infra/`，外部同步快照放 `integrations/`。
- 开发记录放 `docs/development/`，评测说明放 `docs/evaluation/`。历史 ADR、开发记录和 CHANGELOG 中的旧路径保留当时语境；当前路径以本文件为准。
- 覆盖率产物放 `artifacts/coverage/`。`.venv/`、`node_modules/`、`.next/`、各工具缓存和编辑器配置保留工具要求的位置，不作为业务代码归档。
- 根目录保留工作区配置、依赖锁、环境入口、许可证与项目导航；不放散落的业务脚本。

## v3.x monorepo 详图

### `apps/api/` — graphrag-api

```
apps/api/src/graphrag_api/
├── main.py                          # uvicorn 入口（graphrag_api.main:app）
├── app.py                           # FastAPI 组装：/healthz /readyz /v1/ask(/stream) /v1/runs /api/query(deprecated)
├── assembly.py                      # 组合根：索引层 + LangGraph 编排层唯一交汇点
├── config.py                        # pydantic-settings（GRAPHRAG_ 前缀，检索栈可选接线）
├── corpus.py                        # 语料加载（.md/.txt/.jsonl）
├── ingest.py                        # 灌库 CLI：分块→KG→Qdrant→BM25（可选 Neo4j 导出）
├── llm.py                           # OpenAI 兼容 LLM 客户端（httpx，无 SDK 依赖）
├── runtime.py                       # 组件工厂：embedder/vector/bm25/reranker/llm 按配置渐进接入
├── run_store.py                     # 内存 RunStore（TTL 3600s / 容量 100）
├── trace/retrieval_trace.py         # RetrievalTraceExporter（/v1/ask 的 retrieval_trace 字段）
└── mcp/                             # /v1/mcp SSE：search.vector/bm25/kg/web + orchestrate.ask
```

### `apps/web/` — @graphrag/web

```
apps/web/src/
├── app/                             # App Router 页面 + /api/graphrag/[...path] 同源代理（注入 x-api-key）
├── components/flow/                 # React Flow AgentFlow + AuditDrawer（证据轨迹可视化）
└── lib/                             # SSE 解析 / API 客户端
```

### `packages/` — 7 个工作区成员

```
packages/
├── schemas/     src/graphrag_schemas/     evidence / retrieval_trace / crag（CRAGBranch/CRAGDecision 唯一定义）
├── retrieval/   src/graphrag_retrieval/   vector(Qdrant) / bm25(jieba) / kg(Neo4j 多跳) / community(global) / web / reranker(BGE) / contextual
├── parsers/     src/graphrag_parsers/     chunker(语义切分) / late_chunking / markdown
├── kg/          src/graphrag_kg/          extraction(gleaning) / resolution(消歧) / graph_store(networkx) / community(Louvain+摘要) / pagerank(PPR, 归一化校准) / pipeline
├── graph/       src/graphrag_graph/       graph(StateGraph+条件边) / nodes/(planner·retriever·evaluator·rewriter·generator·auditor·fallback) / crag(CragScorer) / claims / dspy_auditor / contracts(Protocol) / json_compat
├── observability/ src/graphrag_observability/ langfuse_tracer(未配置时 NoopTracer) / spans
└── eval/        src/graphrag_eval/        metrics / provenance / adversarial / bench/(questions·corpus·reference_runner·runner·report) / ragas_runner / deepeval_runner
```

## 端到端数据流（一次 /v1/ask）

```
apps/web (Next.js) ─同源代理─> FastAPI /v1/ask (app.py: execute)
  └> LangGraph (graph.py): planner → retriever → evaluator ─┬─use──> generator → auditor → END
                                                            ├─rewrite→ rewriter → retriever
                                                            └─fallback→ fallback → END
  planner:  规则优先（<1ms），不确定时 LLM 兜底；local/global/hybrid 路由
  retriever:asyncio.gather 并发扇出 → merge_hits 去重 → rerank 或多样性选择 → EvidencePack
  evaluator: CragScorer（relevance/coverage + spread 阻尼）→ use/rewrite/fallback
  auditor:  DSPy 或启发式 claims 校验，引用必须 ∈ 有效证据集
  └> AskResponse（answer/citations/evidence_pack/audit/claims/retrieval_trace）→ RunStore
```

索引期（离线）：`GRAPHRAG_CORPUS_PATH` → `kg.build_index`（内存索引，启动即服务）；灌库 CLI 可额外生产 Qdrant/BM25/Neo4j 工件（见 README「检索栈真实化」）。

## 优雅降级

| 故障组件 | 降级行为 |
|----------|----------|
| Qdrant / BM25 / reranker 未配置 | 默认离线模式：内存 KG 两路（PPR + 社区摘要）继续服务，`/readyz` wiring 如实上报 |
| 单路检索异常 | `_fan_out` 记录 error 不炸全局，其余路继续 |
| LLM 未配置/调用失败 | generator 走骨架答案 + 强制引用校验；planner 走规则；auditor 走启发式 claims |
| rerank 失败 | 回退输入截断，检索不中断 |
| Langfuse 未配置 | NoopTracer 全链路 no-op |

## CI / 工作流哨兵模式

CI 模板存放在 `infra/workflows-template/*.tmpl`，执行 `make ci-activate` 同步到已纳入版本管理的 `.github/workflows/` 后一并提交。本地质量门：`make test && make lint && make typecheck`（coverage 门 `fail_under=70`）；确定性评测门：`uv run --package graphrag-eval python -m graphrag_eval.bench --strict`。

## 技术栈快照（v3.x）

| 层级 | 技术 | 用途 |
|------|------|------|
| **Python** | CPython 3.12+ / uv workspace | 后端与各包运行时 |
| **LLM 编排** | LangGraph 0.2.x | 7 节点 Agentic RAG |
| **LLM 接入** | OpenAI 兼容端点（httpx 直连，DeepSeek/智谱/vLLM） | 生成/规划/审计 |
| **向量库** | Qdrant 1.12+（可选接线） | 稠密检索 |
| **图索引** | networkx 内存图（Neo4j 可选导出/查询） | KG 索引与 PPR |
| **关键词检索** | rank-bm25 + jieba | BM25 中文分词 |
| **Rerank** | BAAI FlagEmbedding（可选 extra） | BGE cross-encoder |
| **可观测** | Langfuse（可选） | trace + audit |
| **评测** | 自研确定性 bench + RAGAS/DeepEval 适配 | PS/Recall/Citation/adversarial |
| **后端** | FastAPI + MCP SDK 1.0+ | REST + MCP SSE |
| **前端** | Next.js 15 + React 19 + @xyflow/react | App Router + 证据轨迹可视化 |
| **质量门** | pytest(cov≥70) + ruff + pyright + tsc + Biome | 本地与 CI |

## v1 legacy 子树（保留以供回归对照）

```
legacy/backend/  app/{agents,api,services,utils} + config + tests + main.py
legacy/frontend/ src/app/{chat,graph,status,upload} + Tailwind 4
eval/     questions.json + run_eval.py（旧 5 题口径；v3 契约评测用 graphrag_eval.bench）
```

v1 编排位于 `infra/docker/docker-compose.legacy.yml`，从根目录执行 `make legacy-up` 启动。注意：`legacy/backend/app/agents/orchestrator.py` 已反向接入 v3 `packages/graph`，归档 v1 时需先解耦（见 backlog P3）。
