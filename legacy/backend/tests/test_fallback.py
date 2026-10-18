from app.services.kg_service import KnowledgeGraphService

def test_kg_disconnected_fallback():
    service = KnowledgeGraphService()
    service.driver = None

    stats = service.get_stats()
    neighbors = service.search_neighbors("GraphRAG")

    assert stats["status"] == "disconnected"
    assert neighbors["neighbors"] == []
    assert neighbors["status"] == "disconnected"
