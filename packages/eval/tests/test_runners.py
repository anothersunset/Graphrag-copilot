"""RagasRunner + DeepEvalRunner happy-path adapters with fake evaluate fn."""
from __future__ import annotations

from graphrag_eval.deepeval_runner import DeepEvalRunner
from graphrag_eval.ragas_runner import EvalSample, RagasRunner


SAMPLES = [
    EvalSample(
        question="What is GraphRAG?",
        answer="GraphRAG combines KG with vector retrieval.",
        contexts=["GraphRAG is a hybrid RAG variant."],
        ground_truth="GraphRAG fuses graphs and vectors.",
    ),
]


def test_ragas_runner_uses_injected_evaluate_fn():
    def fake_evaluate(dataset, *, metrics, llm, embeddings):
        assert len(dataset) == 1
        assert set(metrics) == {"context_precision", "context_recall", "faithfulness"}
        return {"context_precision": 0.92, "context_recall": 0.88, "faithfulness": 0.95}

    runner = RagasRunner(evaluate_fn=fake_evaluate)
    out = runner.run(SAMPLES)
    assert out["context_precision"] == 0.92
    assert out["faithfulness"] == 0.95


def test_ragas_runner_empty_input_returns_zeros():
    runner = RagasRunner(evaluate_fn=lambda *_a, **_kw: {})
    out = runner.run([])
    assert all(v == 0.0 for v in out.values())


def test_deepeval_runner_uses_injected_evaluate_fn():
    def fake_evaluate(cases, *, metrics, judge):
        assert cases[0]["input"] == "What is GraphRAG?"
        return {"hallucination": 0.05, "answer_relevancy": 0.91, "bias": 0.02}

    runner = DeepEvalRunner(evaluate_fn=fake_evaluate)
    out = runner.run(SAMPLES)
    assert out["hallucination"] == 0.05
    assert out["answer_relevancy"] == 0.91
