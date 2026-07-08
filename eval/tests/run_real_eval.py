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
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eval.graphrag_client import GoldCase, QueryResult, run_query
from eval.datasets import load_benchmark
from eval.metrics import compute_metrics


def _wait_for_backend(base_url: str, log, max_wait: int = 60):
    """等待后端恢复健康."""
    import urllib.request
    import urllib.error
    for _ in range(max_wait // 5):
        try:
            urllib.request.urlopen(f"{base_url}/health", timeout=5)
            return
        except Exception:
            time.sleep(5)
    log.warning("Backend not healthy after %ds wait", max_wait)


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
    # 配置日志
    log_dir = Path("eval/results")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "real_eval.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode="w", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger("real_eval")

    log.info("=" * 60)
    log.info("GraphRAG Copilot Real Evaluation")
    log.info("=" * 60)

    cases = load_benchmark("eval/datasets/benchmark_50.jsonl")
    if max_cases > 0:
        cases = cases[:max_cases]
    log.info("Loaded %d cases", len(cases))
    log.info("Base URL: %s", base_url)
    log.info("LLM Judge: %s", use_llm)

    results = []
    errors = 0
    start_time = time.time()

    for i, case in enumerate(cases):
        # 每 5 题检查后端健康
        if i > 0 and i % 5 == 0:
            _wait_for_backend(base_url, log)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = run_query(case.question, {"vector": True, "bm25": True, "graph": True}, base_url=base_url)
                point_coverage = check_answer(result.answer, case)
                metrics = compute_metrics(case, result, point_coverage=point_coverage, use_llm=use_llm)

                status = "OK" if point_coverage > 0 else "MISS"
                log.info("[%d/%d] %s %s (%s): acc=%.2f faith=%.2f lat=%.1fs tc=%.2f ac=%.2f",
                         i+1, len(cases), status, case.id, case.type,
                         point_coverage, metrics.get("faithfulness", 0),
                         result.latency, metrics.get("trace_completeness", 0),
                         metrics.get("audit_coverage", 0))

                results.append(metrics)
                break  # 成功，跳出重试循环

            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 10 * (attempt + 1)
                    log.warning("[%d/%d] %s attempt %d failed, retrying in %ds: %s",
                                i+1, len(cases), case.id, attempt+1, wait, str(e)[:80])
                    time.sleep(wait)
                    # 重试前检查后端健康
                    _wait_for_backend(base_url, log)
                else:
                    errors += 1
                    log.error("[%d/%d] ERR %s (after %d attempts): %s",
                              i+1, len(cases), case.id, max_retries, str(e)[:100])

    elapsed = time.time() - start_time

    # 汇总
    log.info("=" * 60)
    log.info("Completed: %d | Errors: %d | Time: %.0fs", len(results), errors, elapsed)
    log.info("=" * 60)

    if not results:
        log.warning("No results to summarize.")
        return

    # 按组汇总
    log.info("%-25s %-10s", "Metric", "Value")
    log.info("-" * 35)

    for metric_key in ["answer_accuracy", "faithfulness", "hallucination_rate",
                        "boundary_refusal_rate", "trace_completeness", "audit_coverage",
                        "verifier_pass_rate", "recall_at_5", "citation_recall"]:
        values = [r[metric_key] for r in results if metric_key in r]
        if values:
            avg = sum(values) / len(values)
            log.info("%-25s %.4f", metric_key, avg)

    # 按类型拆分
    log.info("")
    log.info("%-12s %-12s %-15s %-8s", "Type", "Accuracy", "Faithfulness", "Count")
    log.info("-" * 50)

    for qtype in ["factual", "relational", "multihop", "crossdoc", "boundary"]:
        type_results = [r for r in results if r.get("case_type") == qtype]
        if type_results:
            avg_acc = sum(r["answer_accuracy"] for r in type_results) / len(type_results)
            avg_faith = sum(r["faithfulness"] for r in type_results) / len(type_results)
            log.info("%-12s %-12.4f %-15.4f %-8d", qtype, avg_acc, avg_faith, len(type_results))

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
    log.info("Results saved to: %s", out_file)
    log.info("Log saved to: %s", log_file)


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
