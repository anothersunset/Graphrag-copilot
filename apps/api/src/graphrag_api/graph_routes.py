"""UI-support graph/status endpoints, backed by the in-memory index.

Shapes mirror the legacy v1 service (``kg_service.get_all_graph`` /
``search_neighbors``) so the ported knowledge-graph page works unchanged;
the data source is the boot-built ``GraphRAGIndex`` on ``app.state.index``
instead of Neo4j.
"""

from __future__ import annotations

from collections import deque

from fastapi import APIRouter, HTTPException, Query, Request

from graphrag_api.config import settings

router = APIRouter(prefix="/api")


def _require_index(request: Request):
    index = getattr(request.app.state, "index", None)
    if index is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "not_ready", "message": "index is not loaded"},
        )
    return index


@router.get("/graph")
def full_graph(
    request: Request,
    limit: int = Query(default=500, ge=1, le=2000),
    type: str = Query(default="all"),
):
    """Full node+link lists for the force-directed graph page."""
    index = _require_index(request)
    graph = index.graph.graph

    degrees = dict(graph.degree())
    candidates = [
        (name, data)
        for name, data in graph.nodes(data=True)
        if type == "all" or data.get("type", "Entity") == type
    ]
    candidates.sort(key=lambda pair: -degrees.get(pair[0], 0))
    selected = candidates[:limit]
    selected_ids = {name for name, _ in selected}

    nodes = [
        {
            "id": name,
            "label": name,
            "type": data.get("type", "Entity"),
            "degree": degrees.get(name, 0),
            "confidence": round(float(data.get("confidence", 0.0)), 4),
        }
        for name, data in selected
    ]
    links = [
        {
            "source": a,
            "target": b,
            "relation": sorted(data.get("types", {"RELATED_TO"}))[0],
            "weight": round(float(data.get("weight", 1.0)), 4),
        }
        for a, b, data in graph.edges(data=True)
        if a in selected_ids and b in selected_ids
    ]
    return {"nodes": nodes, "links": links, "status": "connected"}


@router.get("/graph/entity/{entity_name}")
def entity_neighbors(
    request: Request,
    entity_name: str,
    depth: int = Query(default=2, ge=1, le=3),
):
    """BFS neighbors of one entity (legacy ``search_neighbors`` shape)."""
    index = _require_index(request)
    graph = index.graph.graph

    start = index.graph.resolve_name(entity_name)
    if start is None:
        return {"entity": entity_name, "neighbors": [], "status": "connected"}

    visited: dict[str, int] = {start: 0}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if visited[node] >= depth:
            continue
        for neighbor in graph.neighbors(node):
            if neighbor not in visited:
                visited[neighbor] = visited[node] + 1
                queue.append(neighbor)

    neighbors = [
        {
            "name": name,
            "type": graph.nodes[name].get("type", "Entity"),
            "distance": distance,
        }
        for name, distance in sorted(visited.items(), key=lambda pair: pair[1])
        if name != start
    ][:50]
    return {"entity": entity_name, "neighbors": neighbors, "status": "connected"}


@router.get("/graph/stats")
def graph_stats(request: Request):
    index = _require_index(request)
    stats = index.stats()
    graph = index.graph.graph
    node_types: dict[str, int] = {}
    for _, data in graph.nodes(data=True):
        node_type = data.get("type", "Entity")
        node_types[node_type] = node_types.get(node_type, 0) + 1
    return {
        "total_nodes": stats.get("nodes", 0),
        "total_relations": stats.get("edges", 0),
        "node_types": node_types,
        "status": "connected",
    }


@router.get("/system/status")
def system_status(request: Request):
    index = _require_index(request)
    return {
        "status": "running",
        "llm_model": settings.llm_model,
        "llm_wired": settings.llm_base_url is not None,
        "graph_store": {
            "total_nodes": index.stats().get("nodes", 0),
            "total_relations": index.stats().get("edges", 0),
            "communities": index.stats().get("communities", 0),
            "status": "connected",
        },
        "auth_enabled": bool(settings.api_key),
        "run_store": settings.run_store_url or "memory://",
        "readiness": "ready",
    }
