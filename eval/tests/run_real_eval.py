"""端到端评测脚本 — 调用真实后端 API 运行 benchmark.

前置条件:
1. 后端服务运行中 (python -m uvicorn main:app)
2. 已上传文档到知识库 (可选，无文档时测试拒答能力)

用法:
    python eval/tests/run_real_eval.py --smoke          # 单题冒烟
    python eval/tests/run_real_eval.py --full           # 50 题完整评测
    python eval/tests/run_real_eval.py --full --llm     # 使用 LLM Judge 计算 faithfulness
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eval.graphrag_client import GoldCase, QueryResult, run_query
from eval.datasets import load_benchmark
from eval.metrics import compute_metrics


def check_answer(answer: str, case: GoldCase) -> float:
    """检查要点覆盖率 (boundary 类型用拒答正确率)."""
    answer_lower = answer.lower()

    if case.type == "boundary":
        refusal_keywords = [
            "没有找到", "无法回答", "信息不足", "不确定", "不知道",
            "没有相关信息", "知识库中没有", "未提供", "未找到",
            "无法确定", "无法提供", "缺少信息", "没有足够"
        ]
        return 1.0 if any(kw in answer_lower for kw in refusal_keywords) else 0.0

    covered = sum(1 for p in case.gold_answer_points if any(
        p[i:i+4].lower() in answer_lower for i in range(0, len(p), 4)
    ))
    return covered / len(case.gold_answer_points) if case.gold_answer_points else 0.0


def smoke_test(base_url: str):
    """单题冒烟测试."""
    print("=" * 50)
    print("Smoke Test - 验证后端 API")
    print("=" * 50)

    cases = load_benchmark("eval/datasets/benchmark_50.jsonl")
    case = cases[0]
    print(f"Testing: {case.id} - {case.question[:60]}...")

    try:
        result = run_query(case.question, {"vector": True, "bm25": True}, base_url=base_url)
        print(f"[PASS] API OK, latency={result.latency:.1f}s")
        print(f"Answer: {result.answer[:150]}...")
        print(f"Trace nodes: {result.trace_nodes}")
        print(f"Sources: {len(result.contexts)} chunks")
        return True
    except Exception as e:
        print(f"[FAIL] API error: {e}")
        return False


def run_real_eval(base_url: str, use_llm: bool = False, max_cases: int = 0):
    """运行真实评测."""
    print("=" * 60)
    print("GraphRAG Copilot Real Evaluation")
    print("=" * 60)

    cases = load_benchmark("eval/datasets/benchmark_50.jsonl")
    if max_cases > 0:
        cases = cases[:max_cases]
    print(f"Loaded {len(cases)} cases")
    print(f"Base URL: {base_url}")
    print(f"LLM Judge: {use_llm}")
    print()

    results = []
    errors = 0
    start_time = time.time()

    for i, case in enumerate(cases):
        try:
            result = run_query(case.question, {"vector": True, "bm25": True, "graph": True}, base_url=base_url)
            point_coverage = check_answer(result.answer, case)
            metrics = compute_metrics(case, result, point_coverage=point_coverage)

            status = "OK" if point_coverage > 0 else "MISS"
            print(f"[{i+1}/{len(cases)}] {status} {case.id} ({case.type}): acc={point_coverage:.2f} lat={result.latency:.1f}s")

            results.append(metrics)

        except Exception as e:
            errors += 1
            print(f"[{i+1}/{len(cases)}] ERR {case.id}: {str(e)[:60]}")

    elapsed = time.time() - start_time

    # 汇总
    print()
    print("=" * 60)
    print(f"Completed: {len(results)} | Errors: {errors} | Time: {elapsed:.0f}s")
    print("=" * 60)

    if not results:
        print("No results to summarize.")
        return

    # 按组汇总
    print(f"\n{'Metric':<25} {'Value':<10}")
    print("-" * 35)

    for metric_key in ["answer_accuracy", "faithfulness", "hallucination_rate", "boundary_refusal_rate"]:
        values = [r[metric_key] for r in results if metric_key in r]
        if values:
            avg = sum(values) / len(values)
            print(f"{metric_key:<25} {avg:<10.4f}")

    # 按类型拆分
    print(f"\n{'Type':<12} {'Accuracy':<12} {'Faithfulness':<15} {'Count':<8}")
    print("-" * 50)

    for qtype in ["factual", "relational", "multihop", "crossdoc", "boundary"]:
        type_results = [r for r in results if r.get("case_type") == qtype]
        if type_results:
            avg_acc = sum(r["answer_accuracy"] for r in type_results) / len(type_results)
            avg_faith = sum(r["faithfulness"] for r in type_results) / len(type_results)
            print(f"{qtype:<12} {avg_acc:<12.4f} {avg_faith:<15.4f} {len(type_results):<8}")

    # 保存结果
    out_file = Path("eval/results/real_eval_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_url": base_url,
            "n_cases": len(results),
            "elapsed": elapsed,
            "results": results,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults saved to: {out_file}")


def main():
    parser = argparse.ArgumentParser(description="端到端评测脚本")
    parser.add_argument("--smoke", action="store_true", help="单题冒烟测试")
    parser.add_argument("--full", action="store_true", help="完整 50 题评测")
    parser.add_argument("--cases", type=int, default=0, help="限制用例数")
    parser.add_argument("--llm", action="store_true", help="使用 LLM Judge 计算 faithfulness")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端 API 地址")

    args = parser.parse_args()

    if args.smoke:
        success = smoke_test(args.base_url)
        sys.exit(0 if success else 1)
    else:
        max_cases = args.cases if args.cases > 0 else (50 if args.full else 10)
        run_real_eval(args.base_url, use_llm=args.llm, max_cases=max_cases)


if __name__ == "__main__":
    main()
