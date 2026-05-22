# W2 — LangGraph 7-node Agentic RAG orchestrator

**Window**: 2026-05-28 → 2026-06-03  
**Package**: `packages/graph` (`graphrag-graph`)

## Goal

Land the orchestration backbone for v3.1 with full audit trail emission, so
W3-W7 can plug in real retrievers / scorers / LLMs / auditors without
touching the wiring.

## Topology

```text
START → planner → retriever → evaluator
                                  │
                                  ├─[use,      score ≥ 0.7]    → generator → auditor → END
                                  ├─[rewrite,  0.3 ≤ s < 0.7] → rewriter → retriever (loop, cap = 2)
                                  └─[fallback, s < 0.3]         → fallback → END
```

## Locked decisions

| decision                  | value          | rationale                                                                  |
| ------------------------- | -------------- | -------------------------------------------------------------------------- |
| CRAG `use` threshold      | 0.7            | matches CRAG paper baseline; raises bar for direct-answer path             |
| CRAG `rewrite_low`        | 0.3            | below this signal is too weak even for query reformulation                 |
| `max_rewrites`            | 2              | bounds tail latency; empirically rewrites past 2 yield <1pp Recall@5 gain |
| Reducer for hits/audit    | `operator.add` | every node contributes; we want full trace, not just last-write-wins       |
| Component injection       | Protocols      | unit tests can fake every dep; W3-W7 can swap impls without re-wiring      |

## State shape

See `packages/graph/src/graphrag_graph/state.py`. Key invariants:

- `hits` (raw) and `fused_hits` (post-rerank) coexist so we can compute
  recall metrics against the raw set during W5 evaluation.
- `audit` is **append-only**; every node emits exactly one `AuditEntry`,
  giving us a deterministic per-run log for W6 (`AuditEntry` is one of the
  four core schemas in `packages/schemas`).
- `tool_calls` matches the W6 `ToolSpec` shape so the trace can be replayed
  through the MCP server unchanged.

## What lands when

| package side                         | wired in W2 | replaced in |
| ------------------------------------ | ----------- | ----------- |
| planner (LLM call)                   | deterministic stub | W7 (DSPy `Question → Plan`) |
| retriever fan-out                    | sync loop          | W3 (asyncio.gather over 4 routes) |
| reranker                             | naive score sort   | W3 (BGE-Reranker-v2-m3)            |
| CRAG scorer                          | top-1 heuristic    | W4 (DSPy classifier + LLM judge)   |
| query rewriter                       | suffix append      | W4 (LiteLLM + Instructor)          |
| generator (LLM call)                 | skeleton string    | W4 (LiteLLM + Instructor + citations) |
| auditor                              | citation-count heuristic | W7 (DSPy judge)              |
| observability (Langfuse spans)       | not yet            | W5                                  |

## Tests

22 unit tests in `packages/graph/tests/`:

- `test_graph_smoke.py` — happy path with injected fakes + dry-run fallback
- `test_evaluator_thresholds.py` — boundary conditions at 0.30, 0.69, 0.70
- `test_rewriter_cap.py` — graph stops rewriting at `max_rewrites=2`
- `test_routing.py` — conditional edge logic in isolation

Run locally:

```bash
uv run --package graphrag-graph pytest packages/graph -v
```

## Risks

- LangGraph 0.2.x API may shift to 0.3.x mid-project. Pin is `>=0.2.40,<0.3`.
- The `partial(node, config=...)` pattern is a deliberate choice over global
  config; revisit if W7 DSPy modules require their own config protocol.
- `add_conditional_edges` in 0.2.x doesn't natively support "loop cap" —
  enforced inside `_gated_route` instead. Document for reviewers.
