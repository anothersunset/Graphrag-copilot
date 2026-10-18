# GraphRAG Copilot 知识图谱文档

## 1. 图数据库配置

- **数据库**: Neo4j 5.x
- **插件**: APOC（支持高级查询功能）
- **连接**: bolt://localhost:7687
- **认证**: neo4j / graphrag123

## 2. 实体类型

支持以下实体类型：
- Person（人物）
- Organization（组织）
- Product（产品）
- Technology（技术）
- Concept（概念）
- Document（文档）
- Event（事件）
- Location（地点）
- Entity（通用实体）

## 3. 关系类型

支持以下关系类型：
- USES（使用）
- BELONGS_TO（属于）
- DEPENDS_ON（依赖）
- RELATED_TO（相关）
- CAUSES（导致）
- PART_OF（部分）
- COMPARES_WITH（对比）
- CONTAINS（包含）
- CREATED（创建）
- WORKS_FOR（任职）

## 4. 实体抽取流程

- **服务**: llm_service.extract_entities(text)
- **输入**: 文本前 3000 字符
- **输出**: JSON 格式的 entities 和 relations 列表
- **调用位置**: _extract_entities_background（文档上传后的后台任务）
- **写入方式**: kg_service.ingest_knowledge 通过 UNWIND 批量 MERGE 写入 Neo4j

## 5. 图谱查询操作

### 5.1 graph_rag_search(entities, query, depth=2)
- 接收实体列表和查询
- 执行 depth=2 的图遍历
- 返回匹配的实体、关系和路径信息
- 结果被 evidence_fusion_service 融合到最终上下文

### 5.2 search_neighbors(entity_name, depth)
- 查询指定实体的邻居节点
- 返回邻居的名称、类型和关系

### 5.3 find_paths(source, target, max_depth)
- 查找两个实体之间的路径
- 返回路径上的节点和关系

### 5.4 get_stats()
- 返回图谱统计信息：total_nodes, total_relations, node_types

### 5.5 get_all_graph(limit, type)
- 返回全量图谱数据（节点+关系）
- 供前端力导向图使用

## 6. 错误处理

- Neo4j 不可用时，kg_service.graph_rag_search 抛出异常
- RetrievalAgent.hybrid_search 的 try-except 捕获并记录到 warnings
- 向量检索和 BM25 检索仍然正常工作
- evidence_fusion_service.fuse 只融合可用的检索结果
- 系统不会崩溃，只是丢失图谱检索的增益

## 7. 实体抽取失败处理

- 实体抽取在后台任务 _extract_entities_background 中执行
- 如果失败，logger.exception 记录错误日志
- 不影响文档上传的主流程
- 文档仍然可以被向量检索和 BM25 检索
- 只是图谱检索不会有该文档的实体
