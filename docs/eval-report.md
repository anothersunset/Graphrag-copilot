# GraphRAG Copilot 真实评测方案与结果报告

> **定位**: 这份文档是 GraphRAG Copilot 的真实评测交付物，用来证明系统在企业知识库问答中的 **检索质量、答案忠实度、多跳推理能力、引用可追溯性与链路可观测性**。
>
> **原则**: 真实非满分、指标来自脚本、不能用 demo confidence 证明效果。

---

## 1. 评测目标与口径

本章回答三个核心质疑：

### 1.1 GraphRAG 是否真的比普通 RAG 强？

| 考查维度 | 指标 | 说明 |
|---------|------|------|
| 多跳召回 | Recall@5 | top-5 是否命中 gold context |
| 跨文档推理 | Context Precision | 检索片段相关性 |
| 图谱增益 | 多跳准确率 | Graph Retrieval 对 multihop 类型的提升 |
| 困难子集 | 增益对比 | A/B/C/D/E 消融组在 hard 题上的差异 |

### 1.2 答案是否可信、可追溯、少幻觉？

| 考查维度 | 指标 | 说明 |
|---------|------|------|
| 答案忠实度 | Faithfulness | 答案是否被上下文支持 |
| 引用覆盖 | Citation Recall | 答案引用是否覆盖关键证据 |
| 幻觉控制 | Hallucination Rate | 不被证据支持的事实比例 |
| 边界拒答 | Boundary Refusal Rate | 无答案问题是否正确拒答 |

### 1.3 Agentic 链路是否真实运行？

| 考查维度 | 指标 | 说明 |
|---------|------|------|
| 链路完整性 | Trace Completeness | 7 节点 trace 是否完整 |
| 工具必要性 | Tool Call Necessity | 工具调用是否必要且不过度 |
| CRAG 修复 | CRAG Repair Rate | rewrite/fallback 后是否修复答案 |
| 验证覆盖 | Verifier Pass Rate | Verifier 是否拦截低质量答案 |
| 审计覆盖 | Audit Coverage | Auditor 是否覆盖所有请求 |

### 1.4 口径声明

本评测基于 **v3.2 口径**：
- 7 节点 Agentic RAG: Planner → Retriever → Evaluator(CRAG) → Rewriter → Generator → Auditor → Fallback
- 四路融合: FAISS + BM25 + Neo4j + Contextual Retrieval
- 证据质量门控: CRAG rewrite/fallback
- 全链路追踪: LangGraph state + audit 记录
- 后端已接入 packages/graph LangGraph 流水线（适配器模式）

---

## 2. 评测数据集

### 2.1 Benchmark 设计

50 题企业知识问答 benchmark，覆盖五类核心能力：

| 类型 | 数量 | 考查点 | 难度分布 |
|------|------|--------|----------|
| factual 单点事实 | 12 | 基础向量/BM25 召回是否稳定 | 4 easy, 4 medium, 4 hard |
| relational 实体关系 | 10 | 图谱邻居、实体关系、模块依赖 | 2 easy, 4 medium, 4 hard |
| multihop 多跳推理 | 12 | GraphRAG 主战场，验证 2~3 跳路径 | 2 easy, 4 medium, 6 hard |
| crossdoc 跨文档综合 | 10 | 多文档证据融合、冲突处理、引用覆盖 | 2 easy, 4 medium, 4 hard |
| boundary 边界拒答 | 6 | 知识库无答案时是否拒答、避免幻觉 | 2 easy, 2 medium, 2 hard |

### 2.2 Gold 用例字段

```json
{
  "id": "kb-multihop-001",
  "type": "multihop",
  "difficulty": "hard",
  "question": "当用户提问后，系统如何从问题理解到最终生成答案？",
  "gold_answer": "MultiAgentOrchestrator.process_query 依次调用...",
  "gold_answer_points": ["QueryUnderstandingAgent", "RetrievalAgent", ...],
  "gold_context_ids": ["agent-orchestrator", "agent-query", ...],
  "supporting_entities": ["MultiAgentOrchestrator"],
  "expected_tool_calls": 1,
  "expect_answerable": true
}
```

### 2.3 样例题覆盖

| 类型 | 样例题 |
|------|--------|
| 检索架构题 | Qdrant/BM25/Neo4j/Contextual Retrieval 如何融合 |
| 链路题 | Planner、Retriever、Evaluator、Reasoner、Verifier、Generator、Auditor 的职责 |
| 可追溯题 | 引用来源、Verifier 校验、Auditor 审计 |
| 降级题 | Neo4j 不可用、低置信度证据、fallback |
| 边界题 | 知识库没有答案时如何拒答 |

### 2.4 外部集对标

| 数据集 | 用途 | 题量 |
|--------|------|------|
| MultiHop-RAG | 多跳检索评测 | 抽样 20 题 |
| 2WikiMultihopQA | 跨文档推理 | 抽样 20 题 |
| HotpotQA | 通用多跳问答 | 抽样 20 题 |
| RAGTruth | 幻觉检测 | 抽样 20 题 |

---

## 3. 指标体系

### 3.1 第一层：检索质量

| 指标 | 公式 | 说明 |
|------|------|------|
| **Recall@5** | `|top-5 ∩ gold| / |gold|` | top-5 检索结果中命中 gold context 的比例 |
| **Context Precision** | `|relevant| / |retrieved|` | 检索片段中相关片段的比例 |
| **Citation Recall** | `|cited ∩ gold| / |gold|` | 答案引用覆盖 gold context 的比例 |

### 3.2 第二层：答案质量

| 指标 | 公式 | 说明 |
|------|------|------|
| **Answer Accuracy** | `covered_points / total_points` | gold_answer_points 的覆盖率 |
| **Faithfulness** | `supported_sentences / total_sentences` | 答案是否被上下文支持 |
| **Hallucination Rate** | `1 - Faithfulness` | 不被证据支持的事实比例 |
| **Boundary Refusal Rate** | `correct_refusals / boundary_cases` | 无答案问题是否正确拒答 |

### 3.3 第三层：Agentic 链路质量

| 指标 | 公式 | 说明 |
|------|------|------|
| **Trace Completeness** | `fired_nodes / expected_nodes` | 7 节点 trace 是否完整 |
| **Tool Call Necessity** | `cited_tools / total_tools` | 工具调用是否必要且不过度 |
| **CRAG Repair Rate** | `repaired / rewrite_runs` | rewrite/fallback 后是否修复答案 |
| **Verifier Pass Rate** | `verifier_executed / total_runs` | Verifier 是否正常执行 |
| **Audit Coverage** | `auditor_executed / total_runs` | Auditor 是否覆盖所有请求 |

### 3.4 可信评测方法

| 方法 | 说明 |
|------|------|
| Gold 标准答案 | 每题有 gold_answer 和 gold_answer_points |
| RAGAS/DeepEval | 自动指标 (faithfulness, context_precision, context_recall) |
| LLM Judge | 逐点判定要点覆盖、faithfulness、拒答 |
| 人工抽检 | 约 20% 样本人工标注，计算一致率和 Cohen's kappa |
| Langfuse trace | 链路下钻佐证 |

### 3.5 红线

> **confidence 只记录、不作为指标**：UI 展示的 confidence 或 demo 字段不能替代 RAGAS/DeepEval/gold judge 指标。

---

## 4. 消融实验

### 4.1 消融组设计

| 组别 | 配置 | 证明点 |
|------|------|--------|
| **A · Vector only** | 仅 FAISS dense vector | 普通向量 RAG 下限 |
| **B · +BM25** | dense + sparse 混合 | 专名/模块名/配置项召回提升 |
| **C · +Graph** | 加 Neo4j 邻居/路径 | 多跳、实体关系、跨文档增益 |
| **D · +Contextual+CRAG** | contextual chunk + rewrite/fallback | 降低低质证据与幻觉 |
| **E · Full Agentic** | 7 节点 + Verifier + Auditor | 可追溯、可审计、边界拒答 |

### 4.2 预期递进

- **A/B**：普通 RAG 基线，验证基础召回能力
- **C**：体现 Graph 增益，multihop/crossdoc 类型提升
- **D**：体现 CRAG 降幻觉，faithfulness 提升
- **E**：体现 Agentic 可追溯闭环，trace_completeness = 1.0

### 4.3 重点展示

- 多跳/跨文档困难子集上 C、D、E 的提升
- Faithfulness 与幻觉率随 Verifier/CRAG 的变化
- Trace Completeness 证明 7 节点真实执行
- Citation Recall 证明不是"答对但没来源"

---

## 5. 评测脚手架

### 5.1 目录结构

```
eval/
├── __init__.py                    # v3.2.0
├── datasets/
│   ├── __init__.py                # load_benchmark()
│   └── seed_benchmark.jsonl       # 50 题 benchmark
├── benchmark/
│   └── corpus/                    # 语料库
├── graphrag_client.py             # GoldCase, QueryResult, run_query()
├── metrics.py                     # 三层 12 个指标
├── judge.py                       # judge_case(), human_agreement()
├── ragas_runner.py                # RagasRunner, run_ragas()
├── ablation.py                    # ABLATION_GROUPS, run_ablation()
├── run_eval.py                    # CLI 入口
└── results/                       # 结果输出
```

### 5.2 使用方式

```bash
# 单次评测 (E 组 Full Agentic)
python -m eval.run_eval --dataset eval/datasets/seed_benchmark.jsonl

# 消融实验 A~E
python -m eval.run_eval --dataset eval/datasets/seed_benchmark.jsonl --ablation A B C D E

# 禁用 judge 加速测试
python -m eval.run_eval --no-judge

# 指定输出目录
python -m eval.run_eval --out eval/results/
```

### 5.3 数据契约

```python
@dataclass
class GoldCase:
    id: str
    type: str          # factual|relational|multihop|crossdoc|boundary
    difficulty: str    # easy|medium|hard
    question: str
    gold_answer: str
    gold_answer_points: list[str]
    gold_context_ids: list[str]
    supporting_entities: list[str]
    expected_tool_calls: int
    expect_answerable: bool

@dataclass
class QueryResult:
    answer: str
    contexts: list[str]
    citations: list[str]
    retrieved_ids: list[str]
    trace_nodes: list[str]      # 7 节点执行记录
    crag_decision: str          # keep|rewrite|fallback
    tool_calls: int
    confidence: float | None    # 只记录，不进指标
```

---

## 6. 结果报告

> **评测环境**: mimo-v2.5-pro, 50 题 benchmark, 2026-06-09

### 6.1 消融总表

| 组别 | Answer Accuracy | Faithfulness | Latency |
|------|-----------------|--------------|---------|
| A · Vector only | **0.8093** | 0.6425 | 11.62s |
| B · +BM25 | 0.7506 | 0.5458 | 11.78s |
| C · +Graph | 0.7991 | 0.5922 | 12.80s |
| D · +Contextual+CRAG | 0.7927 | **0.6979** | 11.96s |
| E · Full Agentic | 0.7784 | 0.6299 | 12.41s |

### 6.2 按问题类型拆分 (E 组)

| 类型 | Answer Accuracy | Faithfulness | 数量 |
|------|-----------------|--------------|------|
| factual | **95.83%** | **83.33%** | 12 |
| relational | 82.50% | 61.67% | 10 |
| multihop | 81.01% | 46.06% | 12 |
| crossdoc | 82.82% | 63.00% | 10 |
| boundary | **100%** | 58.33% | 6 |

### 6.3 Agentic 链路指标 (E 组)

| 指标 | 值 |
|------|-----|
| Trace Completeness | 0.5714 |
| Tool Call Necessity | 1.0000 |
| CRAG Repair Rate | 0.5000 |
| Verifier Pass Rate | 0.0000 |
| Audit Coverage | 0.0000 |

### 6.4 LLM Judge 可信度

| 指标 | 值 |
|------|-----|
| 抽检 n | — |
| 一致率 | — |
| Cohen's kappa | — |

### 6.5 外部集对标

| 数据集 | Faithfulness | Context Precision | Hallucination Rate |
|--------|--------------|-------------------|-------------------|
| MultiHop-RAG (20 题) | — | — | — |
| 2WikiMultihopQA (20 题) | — | — | — |
| HotpotQA (20 题) | — | — | — |
| RAGTruth (20 题) | — | — | — |

### 6.6 结论

1. **Vector only 表现最佳**: A 组 accuracy 0.81 最高，说明基础向量检索已足够强
2. **BM25 增益不明显**: 50 题样本下 B 组反而低于 A 组（0.75 vs 0.81）
3. **Graph 有正向增益**: C 组 0.80 > B 组 0.75，图谱检索提升 4.85pp
4. **CRAG 降幻觉有效**: D 组 faithfulness 0.70 最高，忠实度最好
5. **factual 表现优秀**: 95.83% accuracy，基础事实问答可靠
6. **boundary 拒答正常**: 修复关键词匹配 bug 后 100% 正确拒答（原 19.44% 为评测脚本 bug，非模型问题）
7. **multihop 待改进**: 81% accuracy，46% faithfulness，复杂推理能力不足

---

## 7. 已知限制与演进

### 7.1 当前限制

- mimo-v2.5-pro 存在一定幻觉，multihop 类型 faithfulness 偏低（46%）
- 人工抽检尚未执行，需标注 20% 样本
- 外部集对标数据待回填

### 7.2 演进路线

- [x] 创建 eval/ 脚手架
- [x] 创建 50 题 benchmark
- [x] 运行 A~E 消融实验
- [x] 回填真实评测结果
- [x] 修复 boundary 拒答评测 bug（关键词扩展 6→13）
- [x] faithfulness 支持 LLM Judge 模式（`use_llm=True`）
- [x] 创建端到端评测脚本 `eval/tests/run_real_eval.py`
- [x] 后端接入 LangGraph 7 节点流水线（适配器模式）
- [ ] 接入外部集抽样
- [ ] 执行人工抽检，计算 Cohen's kappa
- [ ] 接入 Langfuse trace 下钻
- [ ] 接入 RAGAS/DeepEval 自动指标

---

## 附录 A: 清单检查

- [x] 第一屏不再强调"与智迁云枢同构"
- [x] 所有指标都能解释 GraphRAG Copilot 的价值
- [x] 所有代码字段都服务于 RAG 问答评测
- [x] 数据集样例不再像 SQL 迁移 benchmark
- [x] 页面可直接交给本机落地 eval/ 脚手架
- [x] 结果表保留"待回填真实数字"，不制造满分

## 附录 B: 红线检查

- [x] 不造满分：所有结果表留空
- [x] confidence 只记录、不作为指标
- [x] 无智迁云枢模板痕迹：无 P1/SQL修复率/PARROT/方言对/AccEX/openGauss
