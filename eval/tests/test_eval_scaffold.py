"""Eval 脚手架集成测试 - 不依赖外部 API."""
import json
import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eval.graphrag_client import GoldCase, QueryResult
from eval.datasets import load_benchmark
from eval.metrics import (
    compute_metrics,
    recall_at_k,
    context_precision,
    citation_recall,
    trace_completeness,
    tool_call_necessity,
    verifier_pass_rate,
    audit_coverage,
)
from eval.judge import human_agreement
from eval.ablation import ABLATION_GROUPS


def test_gold_case_dataclass():
    """Test GoldCase dataclass creation."""
    case = GoldCase(
        id="test-001",
        type="factual",
        difficulty="easy",
        question="test question",
        gold_answer="test answer",
        gold_answer_points=["point1", "point2"],
        gold_context_ids=["ctx1", "ctx2"],
    )
    assert case.id == "test-001"
    assert case.type == "factual"
    assert case.expect_answerable is True  # default
    print("[PASS] GoldCase dataclass")


def test_query_result_dataclass():
    """Test QueryResult dataclass creation."""
    result = QueryResult(
        answer="test answer",
        contexts=["ctx1"],
        citations=["cite1"],
        retrieved_ids=["id1"],
        trace_nodes=["planner", "retriever"],
        crag_decision="keep",
        tool_calls=1,
        latency=0.5,
    )
    assert result.answer == "test answer"
    assert result.confidence is None  # default
    print("[PASS] QueryResult dataclass")


def test_load_benchmark():
    """Test benchmark loading."""
    cases = load_benchmark("eval/datasets/seed_benchmark.jsonl")
    assert len(cases) == 10
    assert all(isinstance(c, GoldCase) for c in cases)

    # 检查类型分布
    from collections import Counter
    type_dist = Counter(c.type for c in cases)
    assert type_dist["factual"] == 2
    assert type_dist["relational"] == 2
    assert type_dist["multihop"] == 2
    assert type_dist["crossdoc"] == 2
    assert type_dist["boundary"] == 2
    print(f"[PASS] Load benchmark: {len(cases)} cases")


def test_recall_at_k():
    """Test Recall@k calculation."""
    # 完全命中
    assert recall_at_k(["c1", "c2", "c3"], ["c1", "c2"], k=3) == 1.0
    # 部分命中
    assert recall_at_k(["c1", "c3", "c4"], ["c1", "c2"], k=3) == 0.5
    # 无 gold
    assert recall_at_k(["c1"], [], k=1) == 1.0
    print("[PASS] recall_at_k")


def test_trace_completeness():
    """Test trace completeness calculation."""
    # 完整 trace
    full_trace = ["planner", "retriever", "evaluator", "reasoner",
                  "verifier", "generator", "auditor"]
    assert trace_completeness(full_trace) == 1.0

    # 部分 trace
    partial = ["planner", "retriever", "verifier"]
    assert 0 < trace_completeness(partial) < 1.0

    # 空 trace
    assert trace_completeness([]) == 0.0
    print("[PASS] trace_completeness")


def test_tool_call_necessity():
    """Test tool call necessity calculation."""
    # 完全匹配
    assert tool_call_necessity(2, 2) == 1.0
    # 过度调用
    assert tool_call_necessity(4, 2) == 0.5
    # 调用不足
    assert tool_call_necessity(1, 2) == 0.5
    # 无期望
    assert tool_call_necessity(0, 0) == 1.0
    print("[PASS] tool_call_necessity")


def test_compute_metrics():
    """Test full metrics computation."""
    case = GoldCase(
        id="test-001", type="factual", difficulty="easy",
        question="test", gold_answer="test",
        gold_answer_points=["a", "b"], gold_context_ids=["c1", "c2"],
        expected_tool_calls=1
    )
    result = QueryResult(
        answer="test answer", contexts=["ctx1"], citations=["c1"],
        retrieved_ids=["c1", "c3"], trace_nodes=["planner", "retriever", "verifier"],
        crag_decision="keep", tool_calls=1, latency=0.5
    )

    metrics = compute_metrics(case, result, point_coverage=0.5)

    # 检查所有指标存在
    expected_keys = [
        "case_id", "case_type", "difficulty",
        "recall_at_5", "context_precision", "citation_recall",
        "answer_accuracy", "faithfulness", "hallucination_rate", "boundary_refusal_rate",
        "trace_completeness", "tool_call_necessity", "crag_repair_rate",
        "verifier_pass_rate", "audit_coverage",
        "latency", "confidence", "crag_decision",
    ]
    for key in expected_keys:
        assert key in metrics, f"Missing key: {key}"

    # confidence 只记录
    assert metrics["confidence"] is None
    print("[PASS] compute_metrics")


def test_human_agreement():
    """Test human agreement calculation."""
    judge_rows = [
        {"case_id": "c1", "point_coverage": 0.8},
        {"case_id": "c2", "point_coverage": 0.3},
        {"case_id": "c3", "point_coverage": 0.6},
    ]
    human_rows = [
        {"case_id": "c1", "point_coverage": 0.9},
        {"case_id": "c2", "point_coverage": 0.4},
        {"case_id": "c3", "point_coverage": 0.2},
    ]

    result = human_agreement(judge_rows, human_rows)
    assert "agreement_rate" in result
    assert "cohens_kappa" in result
    assert "n_samples" in result
    assert result["n_samples"] == 3
    print("[PASS] human_agreement")


def test_ablation_groups():
    """Test ablation group configurations."""
    assert len(ABLATION_GROUPS) == 5
    assert set(ABLATION_GROUPS.keys()) == {"A", "B", "C", "D", "E"}

    # A 只有 vector
    assert ABLATION_GROUPS["A"]["vector"] is True
    assert ABLATION_GROUPS["A"]["bm25"] is False
    assert ABLATION_GROUPS["A"]["graph"] is False

    # E 全部开启
    assert ABLATION_GROUPS["E"]["vector"] is True
    assert ABLATION_GROUPS["E"]["bm25"] is True
    assert ABLATION_GROUPS["E"]["graph"] is True
    assert ABLATION_GROUPS["E"]["verifier"] is True
    assert ABLATION_GROUPS["E"]["auditor"] is True
    print("[PASS] ablation_groups")


def test_boundary_refusal():
    """Test boundary refusal detection."""
    case = GoldCase(
        id="b1", type="boundary", difficulty="medium",
        question="test", gold_answer="无法回答",
        gold_answer_points=["信息不足"], gold_context_ids=[],
        expect_answerable=False
    )

    # 正确拒答
    result_correct = QueryResult(
        answer="当前知识库中没有找到足够信息回答这个问题。",
        contexts=[], citations=[], retrieved_ids=[],
        trace_nodes=[], crag_decision="keep", tool_calls=0, latency=0.1
    )

    # 错误回答（幻觉）
    result_wrong = QueryResult(
        answer="答案是 42。",
        contexts=[], citations=[], retrieved_ids=[],
        trace_nodes=[], crag_decision="keep", tool_calls=0, latency=0.1
    )

    from eval.metrics import boundary_refusal_rate
    assert boundary_refusal_rate(result_correct, case) == 1.0
    assert boundary_refusal_rate(result_wrong, case) == 0.0
    print("[PASS] boundary_refusal")


def main():
    """Run all tests."""
    print("=" * 50)
    print("Eval Scaffold Integration Tests")
    print("=" * 50)

    tests = [
        test_gold_case_dataclass,
        test_query_result_dataclass,
        test_load_benchmark,
        test_recall_at_k,
        test_trace_completeness,
        test_tool_call_necessity,
        test_compute_metrics,
        test_human_agreement,
        test_ablation_groups,
        test_boundary_refusal,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
