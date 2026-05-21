# graphrag-graph

LangGraph 7-node Agentic RAG orchestrator (v3.1).

## Nodes

1. **planner** — analyse the question, choose retrievers (DSPy signature in W7)
2. **retriever** — fan-out to vector / BM25 / KG / (optional) web; merge + rerank
3. **evaluator** — CRAG scoring → `use` / `rewrite` / `fallback`
4. **rewriter** — query rewrite (capped at `max_rewrites=2`)
5. **generator** — LiteLLM + Instructor structured answer with `[chunk:N]` citations
6. **auditor** — post-generation faithfulness + citation verification
7. **fallback** — explicit low-confidence response

## Topology

```text
START → planner → retriever → evaluator
           ├─[use,      score ≥ 0.7]    → generator → auditor → END
           ├─[rewrite,  0.3 ≤ s < 0.7] → rewriter → retriever (loop, cap = 2)
           └─[fallback, s < 0.3]         → fallback → END
```

## Quick start

```python
from graphrag_graph import build_graph, GraphConfig, initial_state

graph = build_graph(
    GraphConfig(),
    retrievers={"vector": my_vec, "bm25": my_bm25, "kg": my_kg},
    reranker=my_reranker,
    llm_client=my_llm,
    auditor_client=my_auditor,
)
result = graph.invoke(initial_state("What is GraphRAG?"))
print(result["answer"], result["citations"], result["audit"])
```

All component dependencies are **injected via `Protocol` interfaces**
(`graphrag_graph.contracts`), so swapping in real implementations from
`packages/retrieval`, `packages/kg`, etc. requires zero changes to the graph
wiring.

## Tests

```bash
uv run --package graphrag-graph pytest packages/graph -v
```

## Status

W2 (2026-05-28 → 2026-06-03) — wiring + routing + audit emission complete.  
W3 plugs real retrievers, W4 plugs CRAG scorer + chunking, W5 plugs Langfuse
tracing, W7 plugs DSPy planner + auditor.
