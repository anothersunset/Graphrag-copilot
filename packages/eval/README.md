# graphrag-eval

Evaluation tooling for graphrag-copilot.

## What's in here

- **Custom metrics** (`metrics.py`): `trace_completeness`,
  `tool_call_necessity`, `audit_coverage`, `crag_fix_rate`,
  `provenance_sufficiency_score`.
- **RAGAS runner** (`ragas_runner.py`): injectable `evaluate_fn` for
  faithfulness / context-precision / answer-relevance.
- **DeepEval runner** (`deepeval_runner.py`): injectable judge for LLM-
  as-judge metrics.
- **Provenance Sufficiency** (`provenance.py`): pure-Python sentence-
  level sufficiency check, with an injectable entailer hook for
  BGE-Reranker-v2-m3 or a small NLI model.
- **Adversarial harness** (`adversarial.py` + `tests/adversarial/`):
  distractor-node injection across 6 base cases (en + zh, single-hop,
  multi-hop, numeric, date, definition, quantitative).

## Targets (v3.2)

| Metric | Target |
|---|---|
| Trace Completeness | = 1.00 |
| Tool Call Necessity | ∈ [0.9, 1.1] |
| Audit Coverage | = 1.00 |
| CRAG Fix Rate | ≥ 0.70 |
| Provenance Sufficiency | ≥ 0.80 |
| Context Precision (RAGAS) | ≥ 0.80 |
| Faithfulness (RAGAS) | ≥ 0.85 |
| Recall@5 | ≥ 0.85 |
| Adversarial: misled_rate | ≤ 0.10 |
| Adversarial: hallucination_rate | ≤ 0.10 |
| Adversarial: distractor_visited_rate | ≥ 0.50 |

## Running

```bash
uv run --package graphrag-eval pytest packages/eval/tests -q
```

The adversarial suite is part of the same `pytest` run — it ships its
own fake orchestrators so CI never needs Neo4j or a vector DB.
