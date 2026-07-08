# GraphRAG Copilot Agent 架构文档

## 1. 编排器架构

系统有两套编排器实现：

### 1.1 LegacyOrchestrator（旧版 5 节点手动编排）
- QueryUnderstandingAgent → RetrievalAgent → ReasoningAgent → VerificationAgent → GenerationAgent
- 通过 process_query(query, top_k) 方法调用
- 每个阶段的 trace 记录在返回结果中

### 1.2 LangGraphOrchestrator（新版 7 节点流水线）
- planner → retriever → evaluator(CRAG) → [rewriter → retriever] → generator → auditor
- 基于 LangGraph StateGraph 构建
- 支持 CRAG（Corrective RAG）自动路由：use/rewrite/fallback

## 2. Agent 详细接口

### 2.1 QueryUnderstandingAgent
- 方法: analyze(query) → dict
- 输出字段: intent（意图）、entities（实体）、keywords（关键词）、complexity（复杂度）、requires_multi_hop（是否多跳）、query_rewrite（改写后的查询）

### 2.2 RetrievalAgent
- 方法: hybrid_search(query, entities, top_k) → dict
- 调用链路:
  1. embedding_service.embed_query(query) 生成查询向量
  2. vector_store.search(query_embedding, top_k) 向量检索
  3. bm25_store.search(query, top_k) 关键词检索
  4. kg_service.graph_rag_search(entities, query, depth=2) 图谱检索
  5. evidence_fusion_service.fuse(vector_results, bm25_results, graph_results, top_k) 融合结果
- 返回: vector_results, bm25_results, graph_results, combined_context, warnings

### 2.3 ReasoningAgent
- 方法: reason(query, context, analysis) → dict
- 输出字段: answer（答案）、reasoning_path（推理路径）、sources_used（使用的来源）、confidence（置信度）、limitations（局限性）
- 特殊处理: 当 context 为空时，直接返回「当前知识库中没有找到足够信息回答这个问题」

### 2.4 VerificationAgent
- 方法: verify(query, answer, sources) → dict
- 调用: llm_service.verify_answer(question, answer, source_texts)
- 输出字段: is_supported、hallucination_detected、confidence、issues、source_mapping

### 2.5 GenerationAgent
- 方法: generate(reasoning_result, verification_result) → str
- 特殊处理: 当 confidence < 0.6 时，添加警告提示

## 3. 流式编排器

### 3.1 StreamingOrchestrator
- 方法: process_query_stream(query, top_k) → Generator[dict]
- 流程: Phase 1 问题理解 → Phase 2 混合检索 → Phase 3 流式推理（逐 token）→ Phase 4 校验

## 4. 证据融合服务 (EvidenceFusionService)

- 方法: fuse(vector_results, bm25_results, graph_results, top_k) → list
- 融合逻辑: 按内容指纹去重，计算 fusion_score = base_score × type_weight
- 类型权重: vector=0.65, bm25=0.15, graph=0.20
- BM25 过滤: score < 0.1 的结果被过滤
- compress_context: 截取每个片段前 200 字符，减少 LLM 输入长度
