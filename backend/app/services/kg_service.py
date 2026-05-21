"""GraphRAG Copilot - Neo4j 知识图谱服务
注意: Cypher 的 inline property map {name: $name} 用 chr(123)/chr(125) 拼接生成，
以避免源码工具或文本编辑器对花括号的转义/折叠。"""
from typing import List, Dict, Any
from collections import defaultdict
from neo4j import GraphDatabase
from config.settings import settings
from app.core.logger import logger
from app.core.constants import (
    ALLOWED_ENTITY_TYPES,
    ALLOWED_RELATION_TYPES,
    DEFAULT_ENTITY_TYPE,
    DEFAULT_RELATION_TYPE,
)

_LB = chr(123)  # '{'
_RB = chr(125)  # '}'

def safe_label(label: str) -> str:
    return label if label in ALLOWED_ENTITY_TYPES else DEFAULT_ENTITY_TYPE

def safe_relation_type(rel_type: str) -> str:
    return rel_type if rel_type in ALLOWED_RELATION_TYPES else DEFAULT_RELATION_TYPE

class KnowledgeGraphService:
    def __init__(self):
        self.driver = None
        self._connect()

    def _connect(self):
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            self.driver.verify_connectivity()
        except Exception as e:
            logger.warning("Neo4j unavailable, graph features degraded: {}", e)
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def create_entity(self, entity: Dict[str, Any]) -> bool:
        if not self.driver or not entity.get("name"):
            return False

        label = safe_label(entity.get("type", DEFAULT_ENTITY_TYPE))
        query = (
            "MERGE (e:" + label + " " + _LB + "name: $name" + _RB + ") "
            "SET e += $properties "
            "SET e.confidence = $confidence "
            "SET e.updated_at = datetime() "
            "RETURN e"
        )

        with self.driver.session() as session:
            result = session.run(
                query,
                name=entity["name"],
                properties=entity.get("properties", {}) or {},
                confidence=float(entity.get("confidence", 0.8) or 0.8),
            )
            return result.single() is not None

    def create_relation(self, source: str, target: str, relation_type: str, properties: Dict = None) -> bool:
        if not self.driver or not source or not target:
            return False

        rel_type = safe_relation_type(relation_type)
        query = (
            "MATCH (a " + _LB + "name: $source" + _RB + ") "
            "MATCH (b " + _LB + "name: $target" + _RB + ") "
            "MERGE (a)-[r:" + rel_type + "]->(b) "
            "SET r += $properties "
            "SET r.updated_at = datetime() "
            "RETURN r"
        )

        with self.driver.session() as session:
            result = session.run(
                query,
                source=source,
                target=target,
                properties=properties or {},
            )
            return result.single() is not None

    def _batch_merge_entities(self, label: str, rows: List[Dict[str, Any]]) -> int:
        """在一个 session 中批量 MERGE 同 label 的实体。"""
        if not self.driver or not rows:
            return 0
        query = (
            "UNWIND $rows AS row "
            "MERGE (e:" + label + " " + _LB + "name: row.name" + _RB + ") "
            "SET e += row.properties "
            "SET e.confidence = row.confidence "
            "SET e.updated_at = datetime() "
            "RETURN count(e) as cnt"
        )
        try:
            with self.driver.session() as session:
                rec = session.run(query, rows=rows).single()
                return int(rec["cnt"]) if rec else 0
        except Exception:
            logger.exception("批量 MERGE 实体失败 label={}", label)
            return 0

    def _batch_merge_relations(self, rel_type: str, rows: List[Dict[str, Any]]) -> int:
        """在一个 session 中批量 MERGE 同类型的关系。"""
        if not self.driver or not rows:
            return 0
        query = (
            "UNWIND $rows AS row "
            "MATCH (a " + _LB + "name: row.source" + _RB + ") "
            "MATCH (b " + _LB + "name: row.target" + _RB + ") "
            "MERGE (a)-[r:" + rel_type + "]->(b) "
            "SET r += row.properties "
            "SET r.updated_at = datetime() "
            "RETURN count(r) as cnt"
        )
        try:
            with self.driver.session() as session:
                rec = session.run(query, rows=rows).single()
                return int(rec["cnt"]) if rec else 0
        except Exception:
            logger.exception("批量 MERGE 关系失败 type={}", rel_type)
            return 0

    def ingest_knowledge(self, entities: List[Dict], relations: List[Dict]) -> Dict[str, int]:
        """批量 UNWIND 写入: 按 label / rel_type 分组，每组一个 session。
        避免 N 条数据产生 N 个 Neo4j session，显著加速大批量入图。"""
        stats = {"entities_created": 0, "relations_created": 0}
        if not self.driver:
            return stats

        # 按 label 分组
        ent_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for entity in entities:
            name = entity.get("name")
            if not name:
                continue
            label = safe_label(entity.get("type", DEFAULT_ENTITY_TYPE))
            ent_groups[label].append({
                "name": name,
                "properties": entity.get("properties", {}) or {},
                "confidence": float(entity.get("confidence", 0.8) or 0.8),
            })
        for label, rows in ent_groups.items():
            stats["entities_created"] += self._batch_merge_entities(label, rows)

        # 按 rel_type 分组
        rel_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for relation in relations:
            src = relation.get("source")
            tgt = relation.get("target")
            if not src or not tgt:
                continue
            rel_type = safe_relation_type(relation.get("type", DEFAULT_RELATION_TYPE))
            rel_groups[rel_type].append({
                "source": src,
                "target": tgt,
                "properties": relation.get("properties", {}) or {},
            })
        for rel_type, rows in rel_groups.items():
            stats["relations_created"] += self._batch_merge_relations(rel_type, rows)

        return stats

    def search_neighbors(self, entity_name: str, depth: int = 2) -> Dict[str, Any]:
        if not self.driver:
            return {"entity": entity_name, "neighbors": [], "status": "disconnected"}

        depth = max(1, min(depth, 3))
        query = (
            "MATCH path = (start " + _LB + "name: $name" + _RB + ")-[*1.." + str(depth) + "]-(neighbor) "
            "WITH neighbor, min(length(path)) as distance "
            "RETURN DISTINCT neighbor.name as name, labels(neighbor)[0] as type, distance "
            "ORDER BY distance "
            "LIMIT 50"
        )

        with self.driver.session() as session:
            result = session.run(query, name=entity_name)
            neighbors = [
                {"name": r["name"], "type": r["type"], "distance": r["distance"]}
                for r in result
            ]

        return {"entity": entity_name, "neighbors": neighbors, "status": "connected"}

    def find_paths(self, source: str, target: str, max_depth: int = 3) -> List[Dict[str, Any]]:
        if not self.driver:
            return []

        max_depth = max(1, min(max_depth, 4))
        query = (
            "MATCH path = (a " + _LB + "name: $source" + _RB + ")-[*1.." + str(max_depth) + "]-(b " + _LB + "name: $target" + _RB + ") "
            "WITH path, length(path) as path_length "
            "ORDER BY path_length "
            "LIMIT 5 "
            "RETURN [node IN nodes(path) | " + _LB + "name: node.name, type: labels(node)[0]" + _RB + "] as nodes, "
            "[rel IN relationships(path) | type(rel)] as relations"
        )

        with self.driver.session() as session:
            result = session.run(query, source=source, target=target)
            return [{"nodes": r["nodes"], "relations": r["relations"]} for r in result]

    def graph_rag_search(self, query_entities: List[str], query: str, depth: int = 2) -> Dict[str, Any]:
        results = {"entities_found": [], "related_contexts": [], "paths": []}

        for entity in query_entities:
            neighbors = self.search_neighbors(entity, depth)
            results["entities_found"].append(neighbors)

        if len(query_entities) >= 2:
            for i in range(len(query_entities)):
                for j in range(i + 1, len(query_entities)):
                    paths = self.find_paths(query_entities[i], query_entities[j])
                    if paths:
                        results["paths"].append(
                            {"source": query_entities[i], "target": query_entities[j], "paths": paths}
                        )

        seen = set()
        for entity_result in results["entities_found"]:
            for neighbor in entity_result.get("neighbors", []):
                if neighbor["name"] not in seen:
                    seen.add(neighbor["name"])
                    results["related_contexts"].append(neighbor)

        return results

    def get_stats(self) -> Dict[str, Any]:
        if not self.driver:
            return {"status": "disconnected", "total_nodes": 0, "total_relations": 0, "node_types": {}}

        with self.driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            type_stats = session.run(
                "MATCH (n) RETURN labels(n)[0] as type, count(n) as count ORDER BY count DESC LIMIT 10"
            )
            types = {record["type"]: record["count"] for record in type_stats}

        return {
            "status": "connected",
            "total_nodes": node_count,
            "total_relations": rel_count,
            "node_types": types,
        }

    def get_all_graph(self, limit: int = 500, entity_type: str = "all") -> Dict[str, Any]:
        """返回所有节点和关系，用于前端力导向图可视化

        每个节点附带 source 字段供前端跳转：
          - 实体含 source_url 属性 → {kind: 'url', url}
          - 实体含 doc_id 属性 → {kind: 'doc', doc_id}
          - 否则回退 → {kind: 'neo4j', entity: name}（前端打开邻居详情面板）
        """
        if not self.driver:
            return {"nodes": [], "links": [], "status": "disconnected"}

        limit = max(1, min(limit, 2000))
        type_clause = ""
        if entity_type != "all" and entity_type in ALLOWED_ENTITY_TYPES:
            type_clause = ":" + entity_type

        with self.driver.session() as session:
            # 获取节点及其度数（同时取 source_url / doc_id 作为可选跳转目标）
            nodes_query = (
                "MATCH (n" + type_clause + ") "
                "OPTIONAL MATCH (n)-[r]-() "
                "RETURN n.name as id, labels(n)[0] as type, n.name as label, "
                "count(r) as degree, n.confidence as confidence, "
                "n.source_url as source_url, n.doc_id as doc_id "
                "ORDER BY degree DESC "
                "LIMIT $limit"
            )
            nodes_result = session.run(nodes_query, limit=limit)
            nodes = []
            node_ids = set()
            for record in nodes_result:
                nid = record["id"]
                if not nid:
                    continue
                source_url = record["source_url"]
                doc_id = record["doc_id"]
                if source_url:
                    source = {"kind": "url", "url": source_url}
                elif doc_id:
                    source = {"kind": "doc", "doc_id": doc_id}
                else:
                    source = {"kind": "neo4j", "entity": nid}
                nodes.append({
                    "id": nid,
                    "label": record["label"] or nid,
                    "type": record["type"] or "Entity",
                    "degree": record["degree"],
                    "confidence": float(record["confidence"] or 0.0),
                    "exists": True,
                    "source": source,
                })
                node_ids.add(nid)

            # 获取节点之间的关系
            if node_ids:
                links_query = (
                    "MATCH (a)-[r]->(b) "
                    "WHERE a.name IN $names AND b.name IN $names "
                    "RETURN a.name as source, b.name as target, type(r) as relation"
                )
                links_result = session.run(links_query, names=list(node_ids))
                links = [
                    {
                        "source": record["source"],
                        "target": record["target"],
                        "relation": record["relation"],
                        "weight": 0.5,
                    }
                    for record in links_result
                ]
            else:
                links = []

        return {"nodes": nodes, "links": links, "status": "connected"}


kg_service = KnowledgeGraphService()
