# 产品架构说明

## 1. 总体分层
产品架构由三层组成:接入层、检索层、推理层。

### 1.1 接入层
- 文档上传与解析(Markdown / PDF / DOCX)
- 用户与权限管理
- Web 前端与 OpenAPI

### 1.2 检索层
- 向量检索:基于 FAISS,负责语义召回
- 关键词检索:基于 BM25,负责精确命中
- 知识图谱:基于 Neo4j,负责实体与多跳关系
- Evidence Fusion:对三路结果做加权融合与去重

### 1.3 推理层
- Orchestrator:Multi-Agent 编排
- Reasoner Agent:基于证据生成答案
- Verifier Agent:校验答案是否被证据支持
- Fallback:LLM 故障时切换到规则回答

## 2. 与 AI 战略的对应关系
- 检索层对应"短期"阶段的统一知识库
- 知识图谱与 Multi-Agent 对应"中期"阶段
- Agent 平台对应"长期"阶段

## 3. 关键组件负责人
- 检索层组件由"检索组"负责
- 知识图谱组件由"架构组"负责
- Multi-Agent 编排由"平台组"负责
