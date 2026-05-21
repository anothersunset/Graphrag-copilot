"""Build the compiled LangGraph for v3.1.

Topology::

    START → planner → retriever → evaluator
              │           ▲              │
              │           │              ├─[use]→ generator → auditor → END
              │           │              ├─[rewrite, iter<cap]→ rewriter
              │           └─────────────────────────┘
              └──────────────────────────[fallback]→ fallback → END
"""
from __future__ import annotations

from functools import partial
from typing import Any

from langgraph.graph import END, START, StateGraph

from .config import GraphConfig
from .nodes import (
    auditor_node,
    evaluator_node,
    fallback_node,
    generator_node,
    planner_node,
    retriever_node,
    rewriter_node,
)
from .state import GraphState


def build_graph(
    config: GraphConfig | None = None,
    *,
    retrievers: dict[str, Any] | None = None,
    reranker: Any = None,
    llm_client: Any = None,
    auditor_client: Any = None,
    crag_scorer: Any = None,
    query_rewriter: Any = None,
):
    """Build and compile the 7-node Agentic RAG graph.

    All component dependencies are injected; pass real implementations from
    ``packages/retrieval`` / ``packages/kg`` / ``packages/observability`` to
    light the graph up end-to-end. Omit them to get a deterministic skeleton
    that's useful for routing / smoke tests.
    """
    cfg = config or GraphConfig()
    node_cfg: dict[str, Any] = {
        "crag": cfg.crag,
        "max_rewrites": cfg.max_rewrites,
        "max_hits": cfg.max_hits,
        "top_k_after_rerank": cfg.top_k_after_rerank,
        "enable_kg": cfg.enable_kg,
        "enable_web_search": cfg.enable_web_search,
        "auditor_strict": cfg.auditor_strict,
        "planner_model": cfg.planner_model,
        "generator_model": cfg.generator_model,
        "auditor_model": cfg.auditor_model,
        "llm_timeout_s": cfg.llm_timeout_s,
        "retrievers": retrievers or {},
        "reranker": reranker,
        "llm_client": llm_client,
        "auditor_client": auditor_client,
        "crag_scorer": crag_scorer,
        "query_rewriter": query_rewriter,
    }

    g: StateGraph = StateGraph(GraphState)
    g.add_node("planner", partial(planner_node, config=node_cfg))
    g.add_node("retriever", partial(retriever_node, config=node_cfg))
    g.add_node("evaluator", partial(evaluator_node, config=node_cfg))
    g.add_node("rewriter", partial(rewriter_node, config=node_cfg))
    g.add_node("generator", partial(generator_node, config=node_cfg))
    g.add_node("auditor", partial(auditor_node, config=node_cfg))
    g.add_node("fallback", partial(fallback_node, config=node_cfg))

    g.add_edge(START, "planner")
    g.add_edge("planner", "retriever")
    g.add_edge("retriever", "evaluator")
    g.add_conditional_edges(
        "evaluator",
        lambda s: _gated_route(s, cfg.max_rewrites),
        {"use": "generator", "rewrite": "rewriter", "fallback": "fallback"},
    )
    g.add_edge("rewriter", "retriever")
    g.add_edge("generator", "auditor")
    g.add_edge("auditor", END)
    g.add_edge("fallback", END)

    return g.compile()


def _gated_route(state: GraphState, max_rewrites: int) -> str:
    decision = state.get("crag_decision", "fallback")
    if decision == "rewrite" and int(state.get("rewrite_iteration", 0)) >= max_rewrites:
        return "fallback"
    return decision
