# GraphRAG Copilot 知识图谱文档

## 1. 图数据库配置

- 数据库: Neo4j 5.x
- 插件: APOC
- 连接: bolt://localhost:7687

## 2. 实体类型

Person、Organization、Product、Technology、Concept、Document、Event、Location、Entity

## 3. 关系类型

USES、BELONGS_TO、DEPENDS_ON、RELATED_TO、CAUSES、PART_OF、COMPARES_WITH、CONTAINS、CREATED、WORKS_FOR

## 4. 实体抽取流程

- llm_service.extract_entities(text) 接收文本前 3000 字符
- 返回 JSON 格式的 entities 和 relations 列表
- kg_service.ingest_knowledge 通过 UNWIND 批量 MERGE 写入 Neo4j

## 5. 图谱查询操作

- graph_rag_search(entities, query, depth=2) - 实体+关系+路径搜索
- search_neighbors(entity_name, depth) - 邻居查询
- find_paths(source, target, max_depth) - 路径查找
- get_stats() - 统计信息
- get_all_graph(limit, type) - 全量图谱

## 6. 错误处理

- Neo4j 不可用时，kg_service.graph_rag_search 抛出异常
- RetrievalAgent.hybrid_search 的 try-except 捕获并记录到 warnings
- 向量检索和 BM25 检索仍然正常工作
