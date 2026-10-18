# 开发日志：GraphRAG 索引层深度重构（local/global 双路 + PPR + 社区检测）

日期：2026-07-08
模块：`packages/kg`（新）、`packages/graph`、`packages/retrieval`、`apps/api`
主题：把「有图谱骨架但图谱不参与推理」的 v3.2，升级为真正实现 GraphRAG 三条学术主线的 v3.3

---

## 1. 出发点：审查发现的三类问题

全面走读 monorepo（8 包 + v1 legacy）后，把问题归为三类。

### 1.1 会「静默吞掉结果」的接线断点（P0，正确性）

1. **LangGraph state schema 丢字段**。`auditor_node` 返回 `cited_chunk_ids` / `claims`，`retriever_node` 我要新增 `evidence_pack`，但 `GraphState`（TypedDict）没有声明这些键。LangGraph 0.2.x 只保留 schema 里声明过的键，**未声明的节点返回值被静默丢弃**——于是 `/v1/ask` 的 `cited_chunk_ids`、`claims`、`evidence_pack` 永远是空。这是最隐蔽的一个：所有单测（节点级）都过，只有端到端才暴露。
2. **KG 检索的 Cypher 一碰真库就崩**。`packages/retrieval/kg.py` 的 `MATCH p=(e)-[*1..$max_depth]-(n)` —— Cypher **不允许在变长路径边界里用参数**，这是 `SyntaxError`。异常被 `except Exception: return []` 静默捕获，四路检索里的 KG 路直接变成永远返回空。
3. **`apps/api/app.py` import 死路径**：`from graphrag_graph.app import build_graph`（该模块不存在，正确是 `graphrag_graph.build_graph`）；`verdict` 读的是不存在的 `state["verdict"]`（真实键是 `auditor_verdict`）。

> 教训延续 6-11 devlog 的第 6 条：**静默回退比崩溃更危险**。三个断点没有一个会报错，只会让「图谱增强」看起来在跑、实则零贡献。

### 1.2 图谱不参与推理（P0，深度）

`packages/kg` 是空壳（只有 `__version__`），`packages/graph` 的图谱能力止步于「把 KG 命中渲染成一句话塞进证据」。真正的 GraphRAG 三条主线一条都没落地：

- **实体图构建**：v1 按 `name` 逐字 MERGE，`Neo4j`/`neo4j`/`Neo4j 数据库` 变三个孤立节点，多跳路径静默断裂；实体抽取只取文档**前 3000 字**（6-11 devlog 已记为已知短板）。
- **社区检测 / global search**：完全缺失。语料级问题（"这批文档的主要主题？"）在 chunk 检索下**结构上无解**——没有任何单 chunk 含答案。
- **图结构化检索**：KG 只做「命中实体→枚举邻居」，没有把「查询实体经多条加权短路径关联到的 chunk」排上来。

### 1.3 CRAG / rewrite 是「假环路」（P1，质量）

- `evaluator_node` 把 `GraphConfig.crag` 阈值传进了 node config，但默认 `CragScorer()` **从不读取**，阈值形同虚设。
- `rewriter_node` 的无 LLM 兜底是给 query 加 `"(rewrite N)"` 后缀 —— 检索器收到的其实是**同一个查询**，rewrite 环路空转。
- `fallback_node` 硬编码英文，中文提问走到兜底时，下游「拒答检测」（中文关键词）识别不了（这条 6-11 devlog 修过 v1，v3 骨架又退化了）。

---

## 2. 做了什么：对齐 GraphRAG 三条学术主线

新增 `packages/kg`（0.1→0.2，从空壳到 7 模块），全部**离线可跑、无外部服务依赖**（networkx 承载图分析，Neo4j 降级为可选 sink），延续全项目「优雅降级」的一贯姿态。

### 2.1 实体图构建：gleaning 抽取 + 实体消歧

| 能力 | 文件 | 对应研究 |
|------|------|---------|
| **多轮 gleaning 抽取** | `kg/extraction.py::LLMEntityExtractor` | Microsoft GraphRAG (Edge et al., 2024)：单遍抽取系统性漏实体，用「还有很多遗漏，请补充」重复追问，让小模型的抽取召回逼近大模型 |
| **co-occurrence 兜底抽取** | `kg/extraction.py::CooccurrenceExtractor` | 无 LLM 时的确定性降级路径，句窗共现成边 |
| **括号深度 JSON 解析** | `kg/extraction.py::extract_balanced_json` | 复用 6-11 devlog 2.3 的教训：推理模型在 JSON 前吐 thinking token，贪婪正则 `\{[\s\S]*\}` 会跨多个对象。逐字符计深度、跳过字符串字面量内的括号 |
| **实体消歧（两段式）** | `kg/resolution.py::EntityResolver` | 归一化合并（NFKC 全角→半角 + casefold + 去标点）→ 同类型内相似度聚类（注入 embedder 走余弦，否则退 `SequenceMatcher`）。保留所有别名、并集 provenance、按类型门控防止 `Apple(Org)` 与 `apple(Concept)` 误并 |
| **加权图索引** | `kg/graph_store.py::KnowledgeGraphIndex` | networkx 承载；边权=证据置信度累加（重复证据加强边）；导出 `to_neo4j_rows()` 兼容 v1 UNWIND 批量入图 |

对 `Neo4j`/`neo4j`/`Neo4j 数据库` 三形合一，多跳路径不再断裂——直接根治 1.2 里最要命的隐性失败。

### 2.2 global search：Louvain 社区检测 + 社区摘要

| 能力 | 文件 | 对应研究 |
|------|------|---------|
| **层级社区检测** | `kg/community.py::detect_communities` | GraphRAG global search 的索引侧：Louvain（与论文 Leiden 同属模块度最大化族）划分实体图；level-0 里超过 `max_community_size` 的社区再切 level-1，对应论文多层 report 树。`partition_fn` 可注入，`leidenalg` 可平滑替换 |
| **社区摘要** | `kg/community.py::CommunitySummarizer` | 每个社区索引期摘要一次；注入 LLM 走抽象式摘要，否则用「最高度数成员 + 最强关系」模板摘要，保证 global 路离线可用 |
| **社区报告检索** | `retrieval/community.py::CommunityRetriever` | global search 的查询侧：语料级问题在**社区摘要**上检索，而非 raw chunk。token overlap（或注入 embedder）× 社区结构 rank 混合排序，报告 id 作引用、成员 chunk/实体作 provenance 回溯 |

这补齐了整条被完全缺失的 global 主线。

### 2.3 图结构化检索：Personalized PageRank（HippoRAG）

| 能力 | 文件 | 对应研究 |
|------|------|---------|
| **PPR 检索** | `kg/pagerank.py::PPRRetriever` + `ppr_scores` | HippoRAG (Gutiérrez et al., 2024)：查询实体作 personalization 种子，在实体图上跑带权 Personalized PageRank，chunk 得分=其所含实体的 PPR 质量之和。奖励「经多条加权短路径关联」的 chunk，天然处理多跳（质量经桥接实体流动，无需枚举路径） |

实现细节：networkx ≥3.5 的 `pagerank` 依赖 scipy，对这个量级的图太重——**手写带权幂迭代**（悬挂质量回流种子，分布归一），无 scipy 依赖。单测验证质量随图距离衰减、断连分量得 0、质量和=1。

### 2.4 local/global 查询路由（planner）

`graph/nodes/planner.py` 在 fan-out 前先分类，对应 Microsoft GraphRAG 的 local/global 分野与 LightRAG 的双层关键词路由：

- `local`：实体锚定的事实问题 → vector + bm25 + KG(PPR)
- `global`：语料级 sensemaking（"总结/主要主题/overall"）→ community reports
- `hybrid`：既有聚合线索又有具体实体 → 全路

坑点（单测暴露）：jieba 的 `eng` 词性把**每个英文词**都标成实体，导致所有英文句子误判 hybrid。改为只认 Chinese 专名（nr/ns/nt/nz）+ 内嵌大写/数字的 Latin token（`Neo4j`/`GPT-4`）作实体锚。

### 2.5 修复 CRAG / rewrite 假环路

- `evaluator_node` 现在真正把 `GraphConfig.crag` 阈值与 v3.2 新参数注入默认 `CragScorer`。
- **CRAG spread penalty**（对应 6-11 devlog 2.1 的 `spread_factor`）：检索分布过平=排序无信号，按平坦度阻尼终分，防止归一化把弱结果集体抬到高分蒙混。
- **CRAG 语义 judge 钩子**：可注入 LLM-as-judge，语义分与统计分按权混合；judge 抛错绝不影响路由。
- `rewriter_node` 无 LLM 兜底改为**真实改写**：iter1 关键词浓缩（利于 BM25），iter2+ 原问 + salient terms 扩展（扩大向量匹配面）。
- `fallback_node` 按提问语言输出中/英兜底（复活 6-11 devlog 2.6 的修复），并补齐 `cited_chunk_ids=[]`/`claims=[]` 让 state 契约在任意终止分支下一致。

### 2.6 retriever 节点：异步扇出 + EvidencePack 装配

`graph/nodes/retriever.py` 重写：同时兼容 async `aretrieve`（`packages/retrieval` 实现）与 sync `retrieve`（v3.1 Protocol），`asyncio.gather` 并发扇出，慢路不再串行阻塞。装配 v3.2 `EvidencePack`（chunks + 多跳 graph paths + visited nodes + rerank trace），多跳图结构端到端保真。

### 2.7 一键索引 + 组装

- `kg/pipeline.py::build_index`：chunks → 抽取 → 消歧 → 图索引 → 社区检测+摘要，一次调用；注入 LLM 提质，否则全离线。
- `apps/api/assembly.py::build_orchestrator_from_index`：把 `retrieve_kg`→`PPRRetriever`、`retrieve_kg_global`→`CommunityRetriever` 绑到编排器，语料索引后 API 即刻拥有可用（离线质量）的 local/global GraphRAG。

---

## 3. 验证

- 全量单测 **125 → 191 通过**（新增 66：kg 33 + retrieval community 5 + graph planner/crag/retriever/generator 23 + api assembly 5）。
- `ruff check` 新增代码全过。
- 端到端 smoke：`initial_state → build_orchestrator_from_index → invoke`，确认
  - local 问题走 PPR、global 问题走 community reports、hybrid 走全路；
  - `cited_chunk_ids`/`claims`/`evidence_pack` 端到端非空（1.1 的 P0 断点已通）；
  - PPR 质量随图距离衰减、断连分量得 0、质量和=1。

## 4. 仍未做（诚实记录）

- PPR 原始质量（~1e-3）远低于 CRAG 阈值，KG-only 的 local 查询在**无 reranker** 时会走 fallback。真机需接 BGE reranker 或对异构检索分做归一化后再喂 CRAG——这是阈值/归一化问题，非结构问题。
- 社区检测在小图上 Louvain（resolution=1.0）很少留下超大社区，level-1 层级路径目前靠注入 `partition_fn` 做确定性测试覆盖；真实语料上的层级效果需大图验证。
- extraction/summary 的 LLM 质量未接线上模型评测（延续 6-11 devlog 的 API 限流教训，需分批 + 延迟监控）。
