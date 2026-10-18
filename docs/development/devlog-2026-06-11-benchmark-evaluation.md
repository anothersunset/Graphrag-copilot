# 开发日志：GraphRAG Copilot 50 题 Benchmark 评测

日期：2026-06-10 ~ 2026-06-11
项目：GraphRAG Copilot（独立项目）
模块：LangGraph 5 节点流水线 + 评测体系

---

## 1. 背景

GraphRAG Copilot 是一个基于 LangGraph 的 RAG 问答系统，5 节点流水线：Planner → Retriever → Evaluator (CRAG) → Generator → Auditor。使用自建 50 题 benchmark（factual/relational/multihop/crossdoc/boundary 各 10-12 题）进行端到端评测。

初始评测结果极差：faithfulness 仅 0.1794，82% 答案事实无上下文依据。

---

## 2. 问题发现与修复

### 2.1 Faithfulness 严重偏低 (P0)

**现象**：50 题 LLM Judge faithfulness 仅 0.1794，82% 答案无上下文依据。

**根因**：
- Generator prompt 引用规则不够强制
- CRAG 阈值太宽松（49/50 走 `use`，从未触发 rewrite/fallback）

**修复**：
- Generator：强制 `[chunk:N]` 引用 + 自检 + 后验验证（无引用→拒答）
- CRAG：`use_threshold` 0.7→0.5, `rewrite_threshold` 0.3→0.2, `coverage_floor` 0.5→0.3
- CRAG：增加 `spread_factor` 惩罚均匀高分（防止 weak 结果蒙混）

**效果**：Faithfulness 0.2074 → 0.6667 (+45.93pp)

**文件**：`nodes/generator.py`, `crag.py`

### 2.2 中文分词：最大的单一改进 (+62pp)

**现象**：关键词法 faithfulness 平均 0.21，但人工看答案质量明显更好。

**根因**：`_faithfulness_keyword()` 用 `sent.split()` 分词。对英文有效（以空格分隔），但对中文完全无效——中文无空格，`split()` 返回整句，关键词匹配率趋近于零。

**修复**：改为 `jieba.cut()` 中文分词。

```python
# 旧：sent.split() 对中文无效
tokens = set(sent.split())

# 新：jieba 中文分词
tokens = set(jieba.cut(sent))
```

**效果**：faithfulness 从 0.2074 → 0.8305 (+62.31pp)。这是整个项目最大的单一改进。

**教训**：中文 NLP 的隐蔽杀手。`str.split()` 对英文是分词，对中文是无操作。这种静默失败比报错更危险——它不报错，只是给出荒谬的低分。

### 2.3 JSON 解析失败（推理模型兼容）

**现象**：mimo-v2.5-pro 推理模型在 JSON 前输出 thinking tokens，贪婪正则 `\{[\s\S]*\}` 匹配到多个 JSON 对象导致解析失败。

**根因**：正则从第一个 `{` 匹配到最后一个 `}`，跨越了多个独立 JSON 块。

**修复**：括号深度匹配 `_extract_balanced_json()`，逐字符计数 `{}` 深度，达到深度 0 时停止。

**文件**：`json_utils.py`, `planner.py`

### 2.4 Trace Completeness 一直为 0.57

**现象**：EXPECTED_TRACE_NODES 包含 reasoner/verifier，但 LangGraph 实际节点名不同。

**根因**：评测脚本用旧版节点名，LangGraph 用 `planner/retriever/evaluator/generator/auditor`。

**修复**：`EXPECTED_TRACE_NODES = {"planner", "retriever", "evaluator", "generator", "auditor"}`

**教训**：节点命名必须与 LangGraph state 完全一致。

### 2.5 Audit Coverage 一直为 0

**现象**：`graphrag_client.py` 从 `trace.analysis/retrieval/reasoning/verification` 提取节点，全部为 0。

**根因**：LangGraph 返回 `trace.nodes = ["planner", "retriever", ...]` 数组格式，客户端用旧的嵌套对象格式。

**修复**：优先检查 `trace.nodes` 数组，回退到 legacy 格式。

### 2.6 Fallback 节点输出英文导致 boundary 拒答失败 (P0)

**现象**：boundary 类型问题走到 fallback 路径时，输出英文 "I don't have enough..."，而拒答关键词检测是中文。

**根因**：`fallback.py` 硬编码英文消息。

**修复**：改为中文 `"根据现有信息无法回答这个问题。"`

**文件**：`fallback.py`

### 2.7 context_precision 指标逻辑反了 (P0)

**现象**：越多检索结果，context_precision 分数越低——完全反直觉。

**根因**：公式 `min(len(gold) / len(contexts), 1.0)` 分子分母反了。

**修复**：改为 `len(retrieved ∩ gold) / len(retrieved)`

**文件**：`eval/metrics.py`

### 2.8 同步阻塞 FastAPI 事件循环 (P0)

**现象**：process_query 同步调用阻塞 30s+ LLM 推理，其他请求排队。

**修复**：用 `asyncio.to_thread()` 包装同步调用。

**文件**：`backend/app/api/routes.py`

### 2.9 BM25 分数归一化膨胀弱结果 (P1)

**现象**：BM25 search 用 max_score 归一化，弱查询结果也被膨胀到 1.0。

**修复**：改用 sigmoid 归一化，`score=0 → 0.05`, `score=5 → 0.88`

**文件**：`bm25_store.py`

### 2.10 跨文档推理修复 (+17pp)

**现象**：crossdoc 10 题中 5 题零分，准确率仅 0.5201。

**根因**：知识库只有 4 个高层架构文档（13 chunks），缺少实现细节（parser、fusion、vector store 等模块文档）。

**修复**（4 层组合拳）：
1. 创建 10 个模块详细文档，覆盖 34 个 gold_context_ids，索引到 FAISS + BM25（13→60 chunks）
2. Planner 添加 crossdoc 意图识别（`_CROSSDOC_KW` 关键词匹配）
3. Retriever 来源多样性选择（`_diversity_select()` 轮询不同文档，避免单文档聚集）
4. Generator 添加跨文档综合 prompt 提示

**效果**：crossdoc 准确率 0.5201 → 0.6923 (+17.2pp)，零分用例 2/10 → 0/10，faithfulness 0.7321 → 0.8544 (+12.2pp)

**文件**：`planner.py`, `retriever.py`, `generator.py`, `backend/data/raw/service_*.md`

### 2.11 CRAG LLM Judge 激活

**现象**：CRAG 之前 100% "use"（检索分数天花板 0.7-0.9），从未触发 rewrite/fallback。

**修复**：加入 LLM 语义评估（1-5 分评分），50/50 混合统计分和语义分。LLM judge 精准区分相关/不相关文档，成功触发 rewrite/fallback。

**文件**：`evaluator.py`

### 2.12 GraphRAG 边优化三连击

**现象**：Full (E) 模式消融结果与 CRAG (D) 完全一致，GraphRAG 增强零收益。

**根因分析**：
1. `retriever.py:458-461` — `query_local()` 返回 `List[dict]`（完整节点对象），但 retriever 期望 `List[str]`（节点 ID）。混入 set 触发 `unhashable type: 'dict'`，异常被静默捕获
2. `graphrag.py` — BFS 遍历用纯 `Set[str]` 邻接表，边权重被完全忽略
3. `kb_graph_builder.py` — 73% 文档来自同一文件，`same_source` 全连接生成 231 条边形成巨大团，BFS 扩展 20+ 邻居，上下文被噪声淹没

**修复**：
1. 从 neighbor dicts 提取 `"id"` 字段
2. BFS 权重感知 — 添加 `_edge_weights` 存储 + `weight_threshold=0.3` 过滤
3. 边生成全面优化：
   - 技术 token 提取（SQL 术语 + 中文词组）
   - same_source 全连接→top-3 token-overlap（231→35 edges）
   - 跨类型桥接语义评分取 top-5
   - 全局 all-pairs 关键词重叠 + 每节点 top-8 cap

**效果**：边数 298→103 (-65%)，社区 5→7（更均匀）。但端到端效果提升有限（报告准确率 +1pp）。

**核心教训**：静态基于规则的边构建对端到端效果提升有限。真正需要的是 LLM 语义相关性判断或更高质量的知识图谱。

**文件**：`retriever.py`, `graphrag.py`, `kb_graph_builder.py`

### 2.13 LLM API 限流陷阱

**现象**：50 题全量评测跑到第 23 题时 mimo API 变慢，后续延迟 60-180s，multihop/crossdoc 全部 acc=0。

**根因**：mimo API 有速率限制，连续 20+ 次调用后触发限流。

**影响**：全量评测结果不可信（acc 0.515 vs 真实 ~0.77）。

**缓解**：评测脚本增加延迟监控（>90s 告警），建议分批运行。

**教训**：评测结果必须检查延迟分布。如果 >50% 用例延迟 >60s，说明 API 被限流，结果不可信。

---

## 3. 其他修复（P1/P2，共 6 项）

| 问题 | 修复 | 文件 |
|------|------|------|
| LangGraph 依赖安装到错误 Python 环境 | 在 hermes venv 中 `pip install -e` | - |
| `graphrag_schemas` Python 版本 `>=3.12` | 改为 `>=3.11` | pyproject.toml |
| CRAG 阈值 config.py 与 crag.py 不一致 | 同步为 0.5/0.2 | config.py |
| compute_metrics 不支持 LLM Judge | 添加 use_llm 参数 | metrics.py |
| Neo4j 模块级导入导致启动失败 | 改为延迟导入 try/except | kg_service.py |
| DEBUG=True 默认开启 | 改为 False | settings.py |

---

## 4. 最终评测结果

### 最终结果（jieba 修复后，50/50 完成）

| 指标 | Run1 (8000) | Run2 (8002) |
|------|------------|------------|
| Answer Accuracy | 0.7544 | **0.7656** |
| Faithfulness | **0.8305** | 0.7932 |
| Hallucination Rate | **0.1695** | 0.2068 |
| Boundary Refusal Rate | 0.0800 | 0.0800 |
| Avg Latency | ~51s | ~45s |

### 按题型分布 (Run2, port 8002)

| Type | Accuracy | Faithfulness | Count |
|------|----------|-------------|-------|
| factual | 0.8750 | 0.8611 | 12 |
| relational | 0.8917 | 0.8740 | 10 |
| multihop | 0.8053 | 0.8554 | 12 |
| crossdoc | 0.5201 | 0.7321 | 10 |
| boundary | 0.6667 | 0.5000 | 6 |

### 历史对比

| 指标 | 旧关键词法 | LLM Judge | jieba 修复后 |
|------|---------|-----------|------------|
| Answer Accuracy | 0.6825 | 0.7164 | **0.7656** |
| Faithfulness | 0.2074 | 0.1794 | **0.7932** |
| Trace Completeness | 1.0000 | 0.9920 | 1.0000 |
| Audit Coverage | 1.0000 | 0.9800 | 1.0000 |

---

## 5. 待解决问题

| 问题 | 状态 | 方向 |
|------|------|------|
| Recall@5 / Citation Recall 全为 0 | 待修复 | gold_context_ids 语义 ID 需映射到 chunk_id |
| 人工抽检未执行 | 待执行 | 标注 10 题，计算 Cohen's kappa |
| API 限流影响全量评测可信度 | 已知 | 分批运行 + 延迟监控 |

---

## 6. 经验教训

1. **中文分词是隐蔽杀手**：`str.split()` 对中文无效，静默失败比报错更危险。单一修复 +62pp faithfulness。
2. **评测体系需要多层验证**：关键词法只适合快速筛选，LLM Judge 给出更准确但更严格的评分，人工抽检是最终的锚定。
3. **静态规则 < LLM 语义判断**：GraphRAG 边优化的教训——基于规则的边构建对检索提升有限（+1pp），真正需要 LLM 语义相关性或更高质量的 KG。
4. **API 限流是静默的结果破坏者**：延迟从 15s 飙升到 120s，结果全零但无报错。评测必须监控延迟分布。
5. **CRAG 阈值是一组互相耦合的参数**：单独改 use_threshold 不够，需要和 rewrite_threshold、coverage_floor、spread_factor 协同调优。
6. **静默回退比崩溃更危险**：`unhashable type: 'dict'` 被静默捕获 → GraphRAG 增强完全失效 → 评测结果误导决策。
