"""GraphRAG Copilot - Neo4j 知识图谱服务
注意: Cypher 的 inline property map {name: $name} 用 chr(123)/chr(125) 拼接生成，
以避免源码工具或文本编辑器对花括号的转义/折叠。"""
from typing import List, Dict, Any
from neo4j import GraphDatabase
from config.settings import settings
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
            print("Neo4j unavailable, graph features degraded:", e)
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

    def ingest_knowledge(self, entities: List[Dict], relations: List[Dict]) -> Dict[str, int]:
        stats = {"entities_created": 0, "relations_created": 0}

        for entity in entities:
            if self.create_entity(entity):
                stats["entities_created"] += 1

        for relation in relations:
            if self.create_relation(
                relation.get("source"),
                relation.get("target"),
                relation.get("type", DEFAULT_RELATION_TYPE),
                relation.get("properties", {}),
            ):
                stats["relations_created"] += 1

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

kg_service = KnowledgeGraphService()
