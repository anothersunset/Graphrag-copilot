# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 2026-09-23 backlog P0：基线合并 + 评测检索维度修复

- 🧭 检索栈真实化第一阶段（可选接线 + `make ingest` + `/readyz` 如实上报）合入 `main`
- 🆔 v1 检索链路稳定 chunk ID：`{file_name}#{chunk_index}`，vector/BM25 共享，上传路径同步落字段
- 🐛 修复评测客户端字段提取：`retrieved_ids` 恒空与 `citations` 误读路由名（Recall@5 恒 0 的两层根因）
- 🗺️ 新增 `eval/datasets/gold_context_map.json`：34 个语义 gold ID → 真实 chunk ID 人工标注映射 + 完整性单测
- 📊 50 题离线重跑：Recall@5 = 0.4716（修复前恒 0），45/50 题 > 0；结果回写 `eval/results/real_eval_baseline_offline_2026-09-23.json`
- 📝 `docs/eval-report.md` 新增 §6.0.0（根因 + 基线 + 口径声明）；`docs/backlog.md` P0 两项移入已完成区

### v3.1 渐进重构进行中 (W1-W8 · 2026-05-21 → 2026-07-16)

详细计划见 [docs/adr/0001-from-v1-to-v3.1.md](docs/adr/0001-from-v1-to-v3.1.md) 与
[docs/architecture/migration-roadmap.md](docs/architecture/migration-roadmap.md)。

#### W1 D1 (2026-05-21)
- 🎯 锁定 A+ 渐进重构策略（不推倒重建，保留 v1 工程资产）
- 📝 新增 ADR-0001：v1 → v3.1 迁移决策记录
- 📐 新增 v3.1 Final 技术规格文档（7 节点 LangGraph / 4 路检索 / CRAG / Langfuse / RAGAS / MCP）
- 🗺️ 新增 8 周迁移路线图（W1-W8 周度交付物 + 验证指标）
- 🏷️ 修正 README badges 仓库 URL（qsm68p75m6-arch → anothersunset）
- 📣 README 顶部增加 v3.1 重构进行中横幅
- ⚙️ 新增 .editorconfig 与 docs/README.md

## [0.1.0] - 2026-05-17

### v1 Initial Release
- ✅ FastAPI 后端：5 节点 Multi-Agent 编排（Query → Retrieval → Reasoning → Verification → Generation）
- ✅ 三路检索：FAISS + BM25 (rank-bm25 + jieba) + Neo4j 5.x
- ✅ 多模态文档解析：PDF / DOCX / PPTX / 图片 OCR / 音视频 ASR
- ✅ 优雅降级：Neo4j / LLM / Embedding 单点故障兜底
- ✅ 安全：X-API-Key + slowapi 限流
- ✅ 测试：10+ pytest 单测 + test_api.py 冷烟 9 检查点
- ✅ 评测：5 题关键词命中率
- ✅ 前端：Next.js 16 + React 19 + Tailwind 4，4 个页面（chat / graph / status / upload）
- ✅ 容器化：Docker Compose 三容器编排
- ✅ CI：GitHub Actions（pytest + ruff + frontend build）

[Unreleased]: https://github.com/anothersunset/Graphrag-copilot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/anothersunset/Graphrag-copilot/releases/tag/v0.1.0
