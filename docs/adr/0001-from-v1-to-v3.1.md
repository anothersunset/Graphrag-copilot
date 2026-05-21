# ADR-0001 · 从 v1 到 v3.1：选择渐进重构 (A+) 而非推倒重建

| 属性 | 值 |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-05-21 |
| **Decision-maker** | @anothersunset (项目作者) |
| **Affected versions** | 0.1.0 → 1.0.0 |
| **Related** | [v3.1-final-spec.md](../architecture/v3.1-final-spec.md) · [migration-roadmap.md](../architecture/migration-roadmap.md) |

## Context

GraphRAG Copilot v1 已于 2026-05-17 完成首版，**已具备完整可跑的 GraphRAG 系统**：

- ✅ 5 节点 Multi-Agent 自研编排（Query → Retrieval → Reasoning → Verification → Generation）
- ✅ 三路检索：FAISS + BM25 (rank-bm25 + jieba) + Neo4j 5.x
- ✅ 多模态文档解析：PDF / DOCX / PPTX / 图片 OCR / 音视频 ASR
- ✅ 优雅降级（Neo4j / LLM / Embedding 任一失效仍可服务）
- ✅ 10+ pytest 单元测试 + 冷烟脚本 9 检查点 + GitHub Actions CI
- ✅ X-API-Key 鉴权 + slowapi 限流
- ✅ Docker Compose 三容器（Neo4j + Backend + Frontend）
- ✅ Next.js 16 前端 4 页面（chat / graph / status / upload）
- ✅ 智谱 GLM-4-Flash + bge-small-zh-v1.5 (dim 512)

但在 2026-05 重新对标 2024-2025 业界主流 RAG 工程后，识别出 **4 个核心叙事短板**：

1. **编排框架非主流** — 5 节点自研编排不是 LangGraph，简历上"用 LangGraph 做 Agentic RAG"无法成立
2. **缺 trace 可视化** — 推理链只有文字日志，面试演示时无法"看见"证据流与节点决策
3. **评测过于简陋** — 5 题关键词命中率，与 RAGAS / Faithfulness / Context Precision 等业界标准距离明显
4. **召回质量天花板低** — 缺 reranker、缺 Contextual Retrieval (Anthropic 2024)、embedding 仅 512 维

此外还有可加分但非必需的项：MCP server（代码即工具）、DSPy 2.5 自动调 prompt、monorepo 规范度。

## Decision

**采纳方案 A+：渐进重构（incremental refactor），不推倒重建（rewrite from scratch）。**

具体含义：
- **保留** v1 中所有"已经做得不差"的工程资产：`document_parser`（多模态）、`evidence_fusion`、`kg_service`、单元测试、CI、Docker、降级策略、前端 4 页面、`.env` 安全配置
- **重构** 4 个核心叙事短板对应的子系统：编排层、可观测层、评测层、检索质量层
- **新增** monorepo 结构（`apps/api/` + `apps/web/` + `packages/*`）作为重构容器，v1 代码逐周迁入新结构
- **每周保持 main 可跑** — 不允许出现"为了重构主干不可用"的破窗期

## Considered Alternatives

### 方案 A · 推倒重建（rewrite）
- **做法**：清空 main，从零按 v3.1 Final 全新写
- **优点**：commit history 干净；架构 1:1 对齐 spec
- **缺点**：丢失 v1 已有的 10+ 单测、多模态解析、降级策略、前端 4 页面等工程资产；至少 4 周内 main 不可跑；面试演示真空期
- **拒绝理由**：v1 不是"反面教材"，是"未达高分但骨架健康"的项目；推倒等于自废武功

### 方案 B · 归档到 `_legacy/` 后并行新版
- **做法**：把 v1 全部迁到 `_legacy/v1/`，新版在根目录平铺
- **优点**：旧代码可见、可对比
- **缺点**：仓库根目录长期"新旧并存"，第一眼不干净；面试官点开容易迷路
- **拒绝理由**：A+ 用 monorepo `apps/` 实现"新旧分离"已经足够干净，无需 `_legacy/` 命名暴露技术债

### 方案 C · 开新仓 `graphrag-copilot-v2`
- **做法**：当前仓库冻结，新仓重做
- **优点**：两个仓库都干净
- **缺点**：个人品牌分叉（一个项目两个仓库）；旧仓库 README 不打补丁会误导访客；GitHub 贡献热力图被稀释
- **拒绝理由**：代表作品要"一个仓库讲清楚一个故事"

### 为什么 A+ 优于纯 A

| 维度 | A（推倒重建） | A+（渐进重构） |
|---|---|---|
| **v1 工程资产复用率** | 0% | ~60% |
| **main 不可跑窗口期** | W1-W4 (~4 周) | 0（每周可跑） |
| **演示能力延续** | W4 之前断档 | 不断档 |
| **面试叙事强度** | "我从零写了 X" | "我把一个能跑的 v1 通过 7 周渐进重构升级到 v3.1，每周 RAGAS 单调上涨" |
| **风险** | 范围爆炸 / 烂尾 | 局部回滚成本低 |
| **首日 commit 价值** | 项目脚手架（无功能） | ADR + spec + roadmap（可读可评） |

## Consequences

### 正面后果
- ✅ 旧 commit history 完整保留，体现真实工程演进轨迹（面试官加分项）
- ✅ 每周 demo 不中断 — `docker-compose up` 始终可用
- ✅ 简历叙事升级：从"做了 X"到"**把 X 通过 RAGAS 量化升级了 Y%**"
- ✅ v1 vs v3.1 可量化对比（Recall@5、Faithfulness、延迟）作为 README 的"证据墙"，比纯描述更有说服力

### 负面后果与缓解
- ⚠️ commit history 不是"一次性干净的开局" — 但这恰恰是真实工程项目的样子
- ⚠️ 迁移期间 `backend/` 与 `apps/api/` 同时存在 — 通过 ADR-0002（W2 D1 撰写）明确迁移完成的截止线（计划 W4 末删除 `backend/`），避免"半永久双轨"
- ⚠️ 需要时刻警惕"重构变改良"的退化 — 通过每周 Weekly Retro 检查是否漂离 v3.1 Final spec，spec 偏离一律以 ADR 形式记录决策

## Migration Boundary

明确划分什么属于"v1 保留"，什么属于"v3.1 重构"：

| 子系统 | v1 状态 | v3.1 处理 |
|---|---|---|
| `document_parser.py`（多模态解析） | ✅ 完整 | 直接迁移到 `packages/parsers/` |
| `evidence_fusion.py`（证据融合） | ✅ 完整 | 直接迁移到 `packages/fusion/` |
| `kg_service.py`（Neo4j 邻居/路径） | ✅ 完整 | 直接迁移到 `packages/kg/` |
| `orchestrator.py`（5 节点 Multi-Agent） | ⚠️ 需重写 | **重构** 为 LangGraph 7 节点 → `apps/api/app/graph/` |
| `vector_store.py`（FAISS） | ⚠️ 引擎切换 | **切换** 到 Qdrant 1.12+ → `apps/api/app/retrieval/vector.py` |
| `bm25_store.py`（BM25） | ✅ 完整 | 直接迁移到 `apps/api/app/retrieval/keyword.py`（加 Contextual Retrieval 装饰） |
| 单元测试 | ✅ 10+ 用例 | **保留** + 按新模块路径迁移，扩到 ≥70% coverage |
| 前端 4 页面 | ✅ 基本可用 | **重构** 为 shadcn/ui + React Flow trace 可视化 → `apps/web/` |
| Eval 5 题 | ⚠️ 太少且非标准 | **重构** 为 RAGAS + DeepEval + 原创 4 指标，扩到 50+ 题 → `eval/` 升级版 |
| 降级策略 | ✅ 完整 | **保留** 并扩展到 4 路检索（Contextual Retrieval 也加降级） |
| Docker Compose | ✅ 可用 | **扩展** 加入 Qdrant + Langfuse + （Neo4j 保留） |
| 安全（X-API-Key + 限流） | ✅ 完整 | **保留** |

## Validation

判断"重构成功"的客观指标（v3.1 Final spec 锁定，详见 [v3.1-final-spec.md](../architecture/v3.1-final-spec.md)）：

- Context Precision ≥ 0.80
- Faithfulness ≥ 0.85
- Recall@5 ≥ 0.85
- Multi-hop 准确率较 v1 提升 ≥ 15 pp
- 幻觉率 ≤ 10%
- CRAG 修复率 ≥ 70%
- Trace Completeness = 1.00
- Tool Call Necessity ∈ [0.9, 1.1]
- 审计覆盖率 = 1.00
- Test coverage ≥ 70%

每周 Weekly Retro 报告 v1 baseline vs v3.1 current 的对比数据，单调下降即触发 ADR。

## Decision Cadence

- 此 ADR 在 W4 末（chunking + CRAG 完成时）进行一次 mid-mortem review
- 若任一周 Weekly Retro 出现"指标倒退"或"范围爆炸"信号，立即触发 ADR-XXXX 重新评估
- W8 末 release 时撰写 ADR-FINAL 总结整次重构的得失

---
*本 ADR 由项目作者 @anothersunset 与 Notion AI 协作撰写于 2026-05-21（W1 D1），作为 graphrag-copilot 项目自动化执行体系的第一份决策记录。*
