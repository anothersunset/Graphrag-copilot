# graphrag-eval

Evaluation harness for GraphRAG Copilot v3.1.

## Layers

| layer       | source                  | runs in CI? | drives release? |
| ----------- | ----------------------- | ----------- | --------------- |
| RAGAS       | LLM judge (offline)     | optional    | no (manual)     |
| DeepEval    | LLM judge (offline)     | optional    | no (manual)     |
| Custom 4    | pure-Python over audit  | yes         | **yes**         |

The four custom metrics are computed without LLM calls so CI can gate on
them and the project can ship a green release-please run even without a
live LLM provider.

## Custom metrics targets (v3.1 spec)

| metric                | target                  |
| --------------------- | ----------------------- |
| trace_completeness    | 1.00                    |
| tool_call_necessity   | within [0.9, 1.1]       |
| audit_coverage        | 1.00                    |
| crag_fix_rate         | ≥ 0.70                 |

RAGAS / DeepEval targets land separately:

| metric              | target          |
| ------------------- | --------------- |
| Context Precision   | ≥ 0.80          |
| Faithfulness        | ≥ 0.85          |
| Recall@5            | ≥ 0.85          |
| Hallucination rate  | ≤ 0.10          |
