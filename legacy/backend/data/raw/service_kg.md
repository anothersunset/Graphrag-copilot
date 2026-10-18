# service-kg 模块文档

## 概述

`KnowledgeGraphService` 是 GraphRAG Copilot 的知识图谱服务，基于 Neo4j 图数据库实现实体和关系的存储、查询与图遍历。模块位于 `backend/app/services/kg_service.py`，通过单例 `kg_service` 对外提供服务。

## Neo4j 连接

通过 `neo4j.GraphDatabase.driver` 建立 Bolt 协议连接：

- **URI**: `settings.NEO4J_URI`（默认 `bolt://localhost:7687`）
- **认证**: `settings.NEO4J_USER`（默认 `"neo4j"`）/ `settings.NEO4J_PASSWORD`（默认 `"password"`）
- 启动时调用 `driver.verify_connectivity()` 验证连接
- 若 neo4j 包未安装或连接失败，`driver` 设为 `None`，图谱功能降级为不可用

## 实体类型

通过 `ALLOWED_ENTITY_TYPES` 白名单控制，共 9 种：

`Person`, `Organization`, `Product`, `Technology`, `Concept`, `Document`, `Event`, `Location`, `Entity`

`safe_label()` 函数将不在白名单中的类型回退为默认值 `DEFAULT_ENTITY_TYPE = "Entity"`。

## 关系类型

通过 `ALLOWED_RELATION_TYPES` 白名单控制，共 10 种：

`USES`, `BELONGS_TO`, `DEPENDS_ON`, `RELATED_TO`, `CAUSES`, `PART_OF`, `COMPARES_WITH`, `CONTAINS`, `CREATED`, `WORKS_FOR`

`safe_relation_type()` 函数将不在白名单中的类型回退为 `DEFAULT_RELATION_TYPE = "RELATED_TO"`。

## 实体与关系创建

- `create_entity(entity)`: 使用 Cypher `MERGE` 按 name 去重写入，设置 properties、confidence（默认 0.8）和 updated_at。
- `create_relation(source, target, relation_type, properties)`: 使用 `MATCH` + `MERGE` 在两个已存在实体间创建关系。

## 批量写入（ingest_knowledge）

`ingest_knowledge(entities, relations)` 是批量入库的核心方法：

1. 按 entity type 分组，每组调用 `_batch_merge_entities()` 使用 `UNWIND` 批量 MERGE
2. 按 relation type 分组，每组调用 `_batch_merge_relations()` 使用 `UNWIND` 批量 MERGE
3. 返回 `{"entities_created": int, "relations_created": int}` 统计

该设计避免 N 条数据产生 N 个 Neo4j session，显著加速大批量入图。

## 图谱搜索

### search_neighbors(entity_name, depth=2)

从指定实体出发，沿任意方向遍历 `depth` 跳（限制 1~3），返回邻居列表（name、type、distance），按距离排序，限制 50 条。

### graph_rag_search(query_entities, query, depth=2)

RAG 专用的图检索方法：

1. 对每个查询实体调用 `search_neighbors` 获取邻居
2. 若查询实体 >= 2 个，两两调用 `find_paths` 寻找路径
3. 去重合并所有邻居到 `related_contexts`

### find_paths(source, target, max_depth=3)

使用 Cypher 可变长度路径查询，返回最短的 5 条路径，每条包含节点列表和关系类型列表。

## 全图可视化

`get_all_graph(limit=500, entity_type="all")` 返回前端力导向图所需的数据结构：

- **nodes**: id、label、type、degree（连接数）、confidence、source（跳转链接）
- **links**: source、target、relation、weight
- 节点 source 字段根据属性决定跳转类型：`source_url` -> URL 跳转，`doc_id` -> 文档跳转，否则打开邻居详情面板
