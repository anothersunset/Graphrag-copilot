# GraphRAG Copilot — 项目结构（当前快照）

> 本文件描述 **`main` 分支的真实代码布局**，与代码同步维护。v1 单体与 v3.x monorepo 双轨并存，v3.x 是默认开发入口。
>
> 迁移决策见 [`docs/adr/0001-from-v1-to-v3.1.md`](docs/adr/0001-from-v1-to-v3.1.md)、[`docs/adr/0002-monorepo-container.md`](docs/adr/0002-monorepo-container.md)；8 周路线图见 [`docs/architecture/migration-roadmap.md`](docs/architecture/migration-roadmap.md)；待办清单见 [`docs/backlog.md`](docs/backlog.md)。

## 顶层布局（双轨：v1 legacy + v3.x monorepo）

```
Graphrag-copilot/
├── apps/                            # v3.x monorepo — uv workspace 成员
│   ├── api/                         # graphrag-api（FastAPI + MCP server）
│   └── web/                         # @graphrag/web（Next.js 15 + React 19）
│
├── packages/                        # v3.x monorepo — uv workspace 成员（7 个）
│   ├── schemas/                     # graphrag-schemas（Pydantic 类型中枢）
│   ├── retrieval/                   # graphrag-retrieval（Qdrant/BM25/Neo4j/社区/web + BGE rerank）
│   ├── parsers/                     # graphrag-parsers（语义切分 + late chunking）
│   ├── kg/                          # graphrag-kg（gleaning 抽取/消歧/Louvain/PPR，networkx 内存图）
│   ├── graph/                       # graphrag-graph（LangGraph 7 节点 + CRAG + claims + DSPy auditor）
│   ├── observability/               # graphrag-observability（Langfuse tracer + spans）
│   └── eval/                        # graphrag-eval（确定性 bench + RAGAS/DeepEval 适配 + adversarial）
│
├── docs/
│   ├── adr/                         # 架构决策记录（ADR-0001 v1→v3.1、ADR-0002 monorepo）
│   ├── architecture/                # v3.1 final spec / 迁移路线图 / provenance / W2 设计
│   ├── backlog.md                   # 待办与交接清单（P0~P3 优先级）
│   ├── devlog-*.md                  # 4 篇开发记录（CI 修复 / benchmark / KG 索引层 / 合并核实）
│   └── eval-report.md               # 50 题评测报告（含遗留项）
│
├── infra/
│   ├── docker/                      # docker-compose.dev.yml（Qdrant + Neo4j + Langfuse）
│   └── workflows-template/          # CI YAML 模板（*.tmpl，make ci-activate 激活）
│
├── scripts/
│   └── install-workflows.sh         # 渲染 CI 模板到 .github/workflows/
│
├── eval/                            # v1 旧评测脚本 + eval/results/（v3.2 基线与结果持久化）
│
├── backend/                         # v1 legacy — FastAPI 5-Agent 单体（仍可独立 demo）
├── frontend/                        # v1 legacy — Next.js 前端（仍可独立 demo）
├── demo_docs/                       # v3.x 默认演示语料（GRAPHRAG_CORPUS_PATH 默认值）
├── docker-compose.yml               # v1 legacy — 三容器编排（Neo4j + backend + frontend）
├── start.sh / test_api.py           # v1 一键启动 + v3 smoke（/healthz /v1/ask 契约）
│
├── Makefile                         # 统一入口：install / api / web / ingest / test / lint / typecheck / smoke
├── pyproject.toml                   # uv workspace 根 + ruff/pyright/pytest/coverage 配置
└── README.md                        # 项目主文档（含检索栈接线环境变量表）
```

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

仓库根目录**没有** `.github/workflows/`。CI 配置以模板形式存放在 `infra/workflows-template/*.tmpl`，由仓库 owner 一次性执行 `make ci-activate` 渲染后推送。本地质量门：`make test && make lint && make typecheck`（coverage 门 `fail_under=70`）；确定性评测门：`uv run --package graphrag-eval python -m graphrag_eval.bench --strict`。

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
backend/  app/{agents,api,services,utils} + config + tests + main.py
frontend/ src/app/{chat,graph,status,upload} + Tailwind 4
eval/     questions.json + run_eval.py（旧 5 题口径；v3 契约评测用 graphrag_eval.bench）
```

v1 仍可通过仓库根 `docker-compose.yml` 独立启动。注意：`backend/app/agents/orchestrator.py` 已反向接入 v3 `packages/graph`，归档 v1 时需先解耦（见 backlog P3）。
