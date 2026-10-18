# 开发日志：GraphRAG 索引层 与 评测调优分支的合并核实

日期：2026-07-08 ~ 2026-07-09
项目：GraphRAG Copilot
模块：`packages/graph`（planner/retriever/crag/fallback/rewriter）+ 合并流程

---

## 1. 背景

`packages/kg` GraphRAG 索引层（gleaning 抽取、实体消歧、Louvain 社区检测、HippoRAG PPR，见 [devlog-2026-07-08](./devlog-2026-07-08-graphrag-index-layer.md)）提交后 push 到 main 被拒绝：远程 main 已被另一条并行工作线推进 14 个提交——LangGraph 7 节点接入 legacy backend、50 题基准评测调优（crossdoc 准确率 +16.5pp）、DeepSeek LLM 迁移。两边独立重写了 `packages/graph` 里同一批核心节点文件，`git merge` 产生 10 个文件的实质性冲突。

本文记录逐文件核实结论、发现的两处静默 bug，以及最终合并方式——原则是**保留双方已验证的价值，而非简单二选一**。

---

## 2. 逐文件核实与合并

### 2.1 planner.py — 两根正交轴，不是二选一

远程版本是 heuristic-first 的 intent 分类引擎（factual/relational/multihop/compare/summarize/crossdoc，关键词规则打分 + LLM fallback），`needs_kg`/`extra_retrieval` 由 intent 驱动，这是真实 50 题评测调出来的。我的版本是 local/global/hybrid 的 mode 分类，决定 community-report 全局检索要不要加入 fan-out。

这两根轴回答的是不同问题：intent 决定检索该有多"狠"（要不要 KG 查找、要不要加深 top_k），mode 决定要不要走 community summary 路线。合并后两者并存，`plan` 里同时携带 `intent` 和 `mode` 字段。

**坑**：`needs_kg` 现在是 intent-gated 的（只有 multihop/relational/compare/crossdoc 才为 True），单纯的事实问题（factual）不再默认带 KG 检索——这是合理的（KG 对纯事实查询是噪声），但意味着我原来"mode=local 就一定带 retrieve_kg"的测试假设需要改成用会触发 needs_kg 的问句。

### 2.2 crag.py + config.py — 发现一处阈值覆盖静默 bug

远程把 CRAG 阈值调优为 use=0.5 / rewrite=0.2 / coverage_floor=0.3（原 v3.1 spec 的 0.7/0.3/0.5 会导致 49/50 题全走 use，从未真正触发 rewrite/fallback），并加了 always-on 的 spread damping（分数分布过于扁平时按 `0.85 + 0.15*spread_factor` 阻尼）。

**核实中发现的 bug**：`evaluator_node` 在没有显式注入 `crag_scorer` 时，会优先读取 `GraphConfig.crag`（一个锁定在旧值 0.7/0.3 的 `CragThresholds` 实例）来构造 `CragScorer`，这会**悄悄覆盖** `CragScorer` 类自身的新调优默认值。也就是说，即便 `crag.py` 里改了默认阈值，只要走 `build_graph(GraphConfig())` 这条默认路径，实际生效的还是旧阈值——远程那次调优在真实跑图时可能从未生效过。

修复：同步 `CragThresholds` 默认值为 0.5/0.2，并在 docstring 里明确写清楚"这两处必须保持同步"。

我自己加的 judge 混合钩子、可选的 flatness 惩罚保留为默认关闭项，不影响新默认行为。

### 2.3 fallback.py — 一个"可靠"两个字破坏了 eval 检测

我加的中文兜底措辞是"根据现有证据无法**可靠**回答这个问题"，双语（中/英）判断问句语言后分别回复。远程版本纯中文，措辞是"根据现有信息无法回答这个问题"。

**核实发现**：`eval/tests/*.py` 里的 `refusal_keywords` 用的是纯子串匹配，找的是连续出现的"无法回答"四个字。我版本里"可靠"两个字插在中间，导致这个匹配失效——功能上答案没错，但会被评测脚本误判为非拒答，静默拉低 boundary_refusal_rate 指标却不报错。

修复：改回"无法回答"连续出现，保留双语能力。

### 2.4 rewriter.py — 三级优先级

1. 注入的 `query_rewriter`（Protocol，`.rewrite()`）最高优先级——不变。
2. 远程新增：`llm_client` 做真实 LLM 改写（多跳问题拆子问题、补同义词）。
3. 无 LLM 时：我的 jieba 关键词浓缩（iter1）/扩展（iter2+）兜底，比远程原来"(rewrite N)" 式后缀兜底质量高得多（后者会让检索器收到完全相同的查询，rewrite 循环形同虚设）。

### 2.5 retriever.py — 保留 async 扇出 + 找回 crossdoc 优化

我的版本用 `asyncio.gather` 并发扇出，同时兼容 async `aretrieve`（`PPRRetriever`/`CommunityRetriever` 只实现了这个接口）和 sync `retrieve`，并组装 v3.2 EvidencePack。远程用 `ThreadPoolExecutor` 只支持 sync，但带了两个评测验证过的优化：`plan.extra_retrieval` 触发 top_k 翻倍，以及无 reranker 时的 crossdoc 来源多样性选择（`_diversity_select`，轮询不同文档避免单文档聚集）。

合并：保留 async 扇出机制（新检索器的硬需求），把 extra_retrieval 深度缩放和多样性选择原样找回来。

### 2.6 test_api.py vs apps/api/smoke_test.py — 同名不同物

两边都改了根目录的 `test_api.py`，但测的是完全不同的服务：我的版本对着 v1 legacy backend（`/health`、`/api/query` 等，port 8000，10 个检查点，与 README 描述一致）；远程版本对着 v3.x `apps/api`（`/healthz`、`/readyz`、`/v1/ask`，port 8001）。这不是文本冲突，是两份文档漂移到了同一个文件名上。拆成两个文件都保留，没有二选一。

---

## 3. 合并后暴露的次生 bug：EchoLLM 测试桩

`apps/api/tests/test_assembly.py` 里的 `EchoLLM` 测试桩原本只服务 generator 节点：`complete()` 无脑返回固定的"引用答案"字符串，不管 system/user 是什么。合并后 rewriter.py 新增了"用 `llm_client` 做改写"这条路径，会复用同一个 `EchoLLM`——它不看 system prompt，于是 CRAG 重写循环把生成答案文本当成下一轮查询喂回给检索器，PPR 在这段乱码文本里找不到任何实体匹配，`evidence_pack` 全部清零。

现象：`test_evidence_pack_flows_end_to_end` 断言 `pack["visited_nodes"] or pack["graph_paths"]` 失败，两者皆为空列表。

排查路径：打印 `plan`/`tools_to_call`/`tool_calls` 确认检索器确实被正确调用且返回了带 path 的 hit → 打印 `query_rewrites` 才发现改写后的"查询"其实是生成答案原文。

修复：`EchoLLM.complete()` 按 system prompt 是否包含"改写查询"分支——改写请求原样透传 `user`（no-op，不破坏实体词），生成请求才返回固定引用答案，模拟真实多用途 LLM 会区分不同 system prompt 的行为。

**教训**：任何"一个 LLM stub 被多个节点复用"的测试场景，stub 必须像真实模型一样对 system prompt 敏感，否则重构/合并时会产生这类不报错、只是结果全零的次生故障——这正是"静默失败比崩溃更危险"的又一个实例。

---

## 4. 结果

- 全量单测 **191 passed**（graph 52、retrieval 24、kg 33、eval 46、schemas 10、observability 3、parsers 8、api 15）。
- 改动涉及的包 `ruff check` 干净。
- 合并提交 `023695e`，已推送 origin/main。
- 已知缺口：`backend/`（v1 legacy）无独立 venv，本次未能跑其单元测试；该目录本就被项目自身的 ruff/pyright 配置排除在质量门禁外，非本次合并新增的缺口。
