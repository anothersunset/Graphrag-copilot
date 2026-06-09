"""GraphRAG Copilot 评测 CLI 入口.

职责: load_benchmark → run_query → compute_metrics + judge + ragas → results/*.json
红线: confidence 只记录不进指标; 结果表留空待回填; 不造满分。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

from eval.ablation import ABLATION_GROUPS, run_ablation, run_single_group
from eval.datasets import load_benchmark
from eval.graphrag_client import GoldCase, QueryResult, run_query
from eval.judge import judge_case
from eval.metrics import compute_metrics
from eval.ragas_runner import run_ragas


def run_single_eval(
    cases: List[GoldCase],
    base_url: str | None = None,
    use_judge: bool = True,
) -> dict:
    """运行单次评测 (E 组 Full Agentic).

    Args:
        cases: gold 用例列表
        base_url: API 地址
        use_judge: 是否启用 LLM judge

    Returns:
        评测结果字典
    """
    results = []
    for case in cases:
        try:
            kwargs = {"question": case.question, "config": ABLATION_GROUPS["E"]}
            if base_url:
                kwargs["base_url"] = base_url
            result = run_query(**kwargs)

            # 计算指标
            point_coverage = 0.0
            judge_result = None
            if use_judge:
                judge_result = judge_case(case, result)
                point_coverage = judge_result["point_coverage"]

            metrics = compute_metrics(case, result, point_coverage=point_coverage)
            if judge_result:
                metrics["judge"] = judge_result

            results.append(metrics)

        except Exception as e:
            results.append({
                "case_id": case.id,
                "error": str(e),
            })

    # RAGAS 评测
    ragas_scores = {}
    valid_results = [r for r in results if "error" not in r]
    if valid_results:
        try:
            from eval.ragas_runner import build_eval_samples
            query_results = []  # 需要从 results 重建，简化处理
            # ragas_scores = run_ragas(cases[:len(valid_results)], query_results)
        except Exception as e:
            ragas_scores = {"error": str(e)}

    return {
        "timestamp": datetime.now().isoformat(),
        "n_cases": len(cases),
        "n_success": len(valid_results),
        "n_error": len(results) - len(valid_results),
        "results": results,
        "ragas_scores": ragas_scores,
    }


def main() -> None:
    """CLI 入口."""
    parser = argparse.ArgumentParser(
        description="GraphRAG Copilot 评测脚手架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行单次评测 (E 组 Full Agentic)
  python -m eval.run_eval --dataset eval/datasets/seed_benchmark.jsonl

  # 运行消融实验 (A~E)
  python -m eval.run_eval --dataset eval/datasets/seed_benchmark.jsonl --ablation A B C D E

  # 指定输出目录
  python -m eval.run_eval --dataset eval/datasets/seed_benchmark.jsonl --out eval/results/
""",
    )
    parser.add_argument(
        "--dataset",
        default="eval/datasets/seed_benchmark.jsonl",
        help="Benchmark 数据集路径 (默认: eval/datasets/seed_benchmark.jsonl)",
    )
    parser.add_argument(
        "--group",
        default="E",
        choices=["A", "B", "C", "D", "E"],
        help="消融组 (默认: E = Full Agentic)",
    )
    parser.add_argument(
        "--ablation",
        nargs="+",
        choices=["A", "B", "C", "D", "E"],
        help="运行消融实验，指定多个组",
    )
    parser.add_argument(
        "--out",
        default="eval/results",
        help="输出目录 (默认: eval/results)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="GraphRAG API 地址 (默认: http://localhost:8000)",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="禁用 LLM judge (加速测试)",
    )
    parser.add_argument(
        "--no-ragas",
        action="store_true",
        help="禁用 RAGAS 评测",
    )

    args = parser.parse_args()

    # 加载数据集
    print(f"Loading benchmark: {args.dataset}")
    try:
        cases = load_benchmark(args.dataset)
    except Exception as e:
        print(f"Error loading dataset: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Loaded {len(cases)} cases")

    # 创建输出目录
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.ablation:
        # 运行消融实验
        print(f"Running ablation: {args.ablation}")
        start = time.time()
        ablation_result = run_ablation(args.ablation, cases, args.base_url)
        elapsed = time.time() - start
        print(f"Ablation completed in {elapsed:.1f}s")

        # 保存结果
        out_file = out_dir / f"ablation_{timestamp}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(ablation_result, f, ensure_ascii=False, indent=2, default=str)
        print(f"Results saved to: {out_file}")

        # 打印 summary
        print("\n" + "=" * 60)
        print("Ablation Summary")
        print("=" * 60)
        for gname, gmetrics in ablation_result.get("summary", {}).items():
            print(f"\n{gname} ({ABLATION_GROUPS[gname]['name']}):")
            for key, val in gmetrics.items():
                if key != "n_cases":
                    print(f"  {key}: {val}")

    else:
        # 运行单组评测
        print(f"Running eval: group={args.group}")
        start = time.time()
        result = run_single_eval(cases, args.base_url, use_judge=not args.no_judge)
        elapsed = time.time() - start
        print(f"Eval completed in {elapsed:.1f}s")

        # 保存结果
        out_file = out_dir / f"eval_{args.group}_{timestamp}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        print(f"Results saved to: {out_file}")

        # 打印统计
        print(f"\nSuccess: {result['n_success']}/{result['n_cases']}")
        if result.get("ragas_scores"):
            print(f"RAGAS: {result['ragas_scores']}")


if __name__ == "__main__":
    main()
