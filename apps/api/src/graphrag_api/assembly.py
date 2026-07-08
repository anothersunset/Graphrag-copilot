"""Composition root — wire the kg index + retrievers into the orchestrator.

This is where the v3.2 GraphRAG index layer (``graphrag_kg``) meets the
LangGraph orchestrator (``graphrag_graph``). The planner emits two graph
routes; this module binds them to real retrievers:

* ``retrieve_kg``        → ``PPRRetriever``  (HippoRAG local search:
                            Personalized PageRank over the entity graph)
* ``retrieve_kg_global`` → ``CommunityRetriever`` (Microsoft GraphRAG
                            global search over community summaries)

``build_orchestrator_from_index`` takes a ready ``GraphRAGIndex`` (built
offline via ``graphrag_kg.build_index``) plus optional vector/bm25/rerank/
LLM components, and returns a compiled graph. Nothing here needs a live
Neo4j/Qdrant — the index is self-contained — so the API can boot into a
fully functional (if offline-quality) GraphRAG the moment a corpus is
indexed.
"""

from __future__ import annotations

import logging
from typing import Any

from graphrag_graph import GraphConfig, build_graph
from graphrag_kg import GraphRAGIndex
from graphrag_retrieval.community import CommunityRetriever

logger = logging.getLogger(__name__)


def build_retrievers(
    index: GraphRAGIndex,
    *,
    vector: Any | None = None,
    bm25: Any | None = None,
    ppr_kwargs: dict | None = None,
) -> dict[str, Any]:
    """Assemble the tool-name → retriever map the retriever node expects.

    Keys must match ``planner`` tool names with the ``retrieve_`` prefix
    stripped: ``vector`` / ``bm25`` / ``kg`` / ``kg_global`` / ``web``.
    """
    retrievers: dict[str, Any] = {
        "kg": index.ppr_retriever(**(ppr_kwargs or {})),
        "kg_global": CommunityRetriever(index.communities, prefer_level=0),
    }
    if vector is not None:
        retrievers["vector"] = vector
    if bm25 is not None:
        retrievers["bm25"] = bm25
    return retrievers


def build_orchestrator_from_index(
    index: GraphRAGIndex,
    *,
    config: GraphConfig | None = None,
    vector: Any | None = None,
    bm25: Any | None = None,
    reranker: Any = None,
    llm_client: Any = None,
    auditor_client: Any = None,
    crag_scorer: Any = None,
    query_rewriter: Any = None,
    planner_client: Any = None,
    ppr_kwargs: dict | None = None,
):
    """Compile a graph whose KG routes are served by the index."""
    cfg = config or GraphConfig(enable_global_search=bool(index.communities))
    retrievers = build_retrievers(index, vector=vector, bm25=bm25, ppr_kwargs=ppr_kwargs)
    logger.info(
        "assembled orchestrator: routes=%s communities=%d",
        sorted(retrievers),
        len(index.communities),
    )
    return build_graph(
        cfg,
        retrievers=retrievers,
        reranker=reranker,
        llm_client=llm_client,
        auditor_client=auditor_client,
        crag_scorer=crag_scorer,
        query_rewriter=query_rewriter,
        planner_client=planner_client,
    )
