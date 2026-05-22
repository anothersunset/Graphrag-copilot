# GraphRAG Copilot — 项目结构（v3.2 当前快照）

> 本文件描述 **`feat/v3.2-bench` 分支上的真实代码布局**——v1 单体与 v3.1 monorepo 当前并存，v3.2 在 `packages/graph` 与 `packages/eval` 内部增量演进。
>
> 完整迁移决策见 [`docs/adr/0001-from-v1-to-v3.1.md`](docs/adr/0001-from-v1-to-v3.1.md)、monorepo 决策见 [`docs/adr/0002-monorepo-container.md`](docs/adr/0002-monorepo-container.md)，8 周路线图见 [`docs/architecture/migration-roadmap.md`](docs/architecture/migration-roadmap.md)。

## 顶层布局（双轨：v1 legacy + v3.x monorepo）

```
Graphrag-copilot/
├── apps/                            # v3.1 monorepo — uv workspace 成员
│   ├── api/                         # graphrag-api（FastAPI + MCP server）
│   └── web/                         # @graphrag/web（Next.js 15 + React 19）
│
├── packages/                        # v3.1 monorepo — uv workspace 成员
│   ├── schemas/                     # graphrag-schemas（Pydantic 类型中枢）
│   ├── retrieval/                   # graphrag-retrieval（4 路检索 + BGE rerank）
│   ├── parsers/                     # graphrag-parsers（语义切分 + late chunking）
│   ├── kg/                          # graphrag-kg（Neo4j 3-hop 子图）
│   ├── graph/                       # graphrag-graph（LangGraph 7 节点 + v3.2 EvidencePack/claims/provenance）
│   ├── observability/               # graphrag-observability（Langfuse trace + audit）
│   └── eval/                        # graphrag-eval（RAGAS + DeepEval + v3.2 adversarial/bench）
│
├── docs/
│   ├── adr/                         # 架构决策记录（ADR-0001 v1→v3.1、ADR-0002 monorepo）
│   └── architecture/                # v3.1 final spec / 迁移路线图 / 7 节点设计
│
├── infra/
│   ├── docker/                      # docker-compose.dev.yml（Qdrant + Neo4j + Langfuse + api + web）
│   └── workflows-template/          # CI YAML 模板（*.tmpl，未激活的哨兵模式）
│
├── scripts/
│   └── install-workflows.sh         # `make ci-activate` 渲染模板到 .github/workflows/
│
├── eval/                            # v1 旧评测脚本 + v3.2 results/ 持久化目录
│
├── backend/                         # v1 legacy — FastAPI 单体（仍可独立 demo）
├── frontend/                        # v1 legacy — Next.js 16（仍可独立 demo）
├── demo_docs/                       # v1 legacy — 演示文档
├── docker-compose.yml               # v1 legacy — 三容器编排（Neo4j + backend + frontend）
├── start.sh / test_api.py           # v1 legacy — 一键启动 + 冷烟脚本
│
├── Makefile                         # 统一入口：install / dev / test / lint / ci-activate
├── pyproject.toml                   # uv workspace 根（v3.x 所有 Python 包）
└── README.md                        # 项目主文档
```

## v3.1/v3.2 monorepo 详图

### `apps/api/` — graphrag-api
```
apps/api/
├── pyproject.toml                   # 依赖：schemas + graph + retrieval + observability
├── src/graphrag_api/
│   ├── main.py                      # FastAPI 应用入口
│   ├── routes/                      # /query /trace /audit /graph /upload
│   ├── mcp/                         # MCP server endpoint（W6）
│   └── settings.py                  # Pydantic Settings
└── tests/                           # routes + MCP 单测
```

### `apps/web/` — @graphrag/web
```
apps/web/
├── package.json                     # Next.js 15 + React 19 + Biome
├── src/app/                         # App Router（chat / trace / graph 三视图）
└── tsconfig.json
```

### `packages/` — 7 个工作区成员
```
packages/
├── schemas/         src/graphrag_schemas/      EvidencePack / TraceRow / RetrievalResult / Claim / ProvenanceReport
├── retrieval/       src/graphrag_retrieval/    vector_retriever / bm25_retriever / kg_retriever / web_retriever / bge_reranker
├── parsers/         src/graphrag_parsers/      semantic_splitter / markdown_aware / late_chunking
├── kg/              src/graphrag_kg/           neo4j_client / entity_extractor / three_hop_subgraph
├── graph/           src/graphrag_graph/        nodes/ (7 LangGraph 节点) · evidence.py · claims.py · provenance.py · adversarial.py
├── observability/   src/graphrag_observability/ langfuse_client / audit_writer / trace_decorators
└── eval/            src/graphrag_eval/         metrics/ · ragas_adapter / deepeval_adapter / bench/ (v3.2 端到端基准)
```

## v3.2 增量交付（位于 `packages/graph` + `packages/eval`）

| 文件 | 功能 | 引入 commit |
|------|------|------------|
| `packages/graph/src/graphrag_graph/evidence.py` | `EvidencePack` 容器 + `GraphPath`/`GraphRel`/`RerankTraceRow` | `f53fc1e6` |
| `packages/graph/src/graphrag_graph/claims.py` | 句级声明抽取 + 异步 entailer 钩子 | `5a36f551` |
| `packages/graph/src/graphrag_graph/provenance.py` | `provenance_sufficiency` 指标 + `query_history` 隔离 | `af04b315` |
| `packages/eval/src/graphrag_eval/adversarial.py` | `DistractorCase` + 干扰对抗框架（misled / hallucination / distractor_visited） | `5ee542ff` |
| `packages/eval/src/graphrag_eval/bench/` | 端到端 zh+en gold + adversarial 基准（reference_runner + CLI） | `a9b9a6ee` |
| `eval/results/v3.2-provenance-baseline.md` | v3.2 基线 KPI 报告 | `a9b9a6ee` |

## CI / 工作流哨兵模式

仓库根目录**没有** `.github/workflows/`。CI 配置以模板形式存放在 `infra/workflows-template/*.tmpl`，由仓库 owner 在本地一次性执行：

```bash
make ci-activate    # 调用 scripts/install-workflows.sh
git push            # 推 .github/workflows/* 到远端
```

采用这种模式是因为 MCP/Actions OAuth 令牌通常没有 `workflow` scope，无法代写 `.github/workflows/`。激活后 PR #3~#6 才能跑 pytest + ruff + pyright。

## 技术栈快照（v3.x）

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **Python** | CPython | 3.12+（root 强制） / 包级 3.11+ | 后端与各包运行时 |
| **包管理** | uv | latest | workspace + lock + sync |
| **LLM 编排** | LangGraph | 0.2.40+ | 7 节点 Agentic RAG |
| **LLM SDK** | litellm + instructor | — | 多模型 + 结构化输出 |
| **向量库** | Qdrant | 1.12+ | HNSW 向量检索 |
| **图数据库** | Neo4j | 5.20+ | 3-hop 子图 |
| **关键词检索** | rank-bm25 + jieba | — | BM25 中文分词 |
| **Rerank** | BAAI FlagEmbedding | — | BGE cross-encoder |
| **可观测** | Langfuse | 2.50+ | trace + audit |
| **评测** | RAGAS + DeepEval + 自研 | — | Recall/Precision/Faithfulness/PS |
| **后端** | FastAPI + MCP SDK | 0.115 / 1.0+ | REST + MCP server |
| **前端** | Next.js + React | 15 / 19 | App Router |
| **类型检查** | Pyright basic（W7 → strict） | — | Python 类型 |
| **Lint/Format** | Ruff + Biome | — | Python + TS |

## v3.x 端到端数据流（LangGraph 7 节点）

```
UserQuery → QueryUnderstanding → Retrieval (vector‖bm25‖kg‖web)
          → Rerank (BGE cross-encoder)
          → CRAG  (relevance gate + web fallback)
          → Reasoning (multi-hop with EvidencePack)
          → Verification (claims + provenance_sufficiency)
          → Generation (answer + citations + confidence)
          ↘ Langfuse trace · audit JSON · query_history per session
```

## 优雅降级（继承自 v1，v3.x 仍保留）

| 故障组件 | 降级行为 |
|----------|----------|
| Neo4j | vector + BM25 + web 三路继续，KG 路径返回空 |
| Qdrant | BM25 独立工作，向量召回缺失走 CRAG web fallback |
| LLM | 返回原始检索证据 + 失败标记，不编造 |
| Embedding | md5 hash 备选向量（精度降低） |

## v1 legacy 子树（保留以供回归对照）

```
backend/  app/{agents,api,services,utils} + config + tests + main.py + requirements.txt
frontend/ src/app/{chat,graph,status,upload} + Next.js 16 + Tailwind 4
eval/     questions.json + run_eval.py（旧 5 题关键词命中率）
```

v1 子树仍可通过仓库根的 `docker-compose.yml` 单独启动，方便与 v3.x 做对照。最终 v3.1 GA 后将归档 v1 至 `legacy/` 或独立 tag，时间表见迁移路线图。
