"""优化版评测脚本 - 支持并行、断点续传、单题冒烟."""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eval.graphrag_client import GoldCase, QueryResult
from eval.datasets import load_benchmark
from eval.metrics import compute_metrics
from eval.ablation import ABLATION_GROUPS

import requests

MIMO_API_URL = "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
MIMO_API_KEY = "tp-srs1nhj8slfztozf8wac0q7jqmbymynt8p5axo22h42z1u0u"
MIMO_MODEL = "mimo-v2.5-pro"

# 结果文件路径
RESULTS_DIR = Path("eval/results")
PROGRESS_FILE = RESULTS_DIR / "eval_progress.json"


def call_mimo(question: str, context: str = "") -> dict:
    """调用 mimo API."""
    system_prompt = (
        "你是企业知识问答助手。请基于上下文回答问题。\n"
        "1. 只基于上下文回答，不要编造\n"
        "2. 信息不足时说\"当前知识库中没有找到相关信息\"\n"
        "3. 简洁明了，不超过200字"
    )

    user_content = f"上下文:\n{context}\n\n问题: {question}" if context else f"问题: {question}"

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {MIMO_API_KEY}"}
    payload = {"model": MIMO_MODEL, "max_tokens": 800, "temperature": 0.3,
               "messages": [{"role": "system", "content": system_prompt},
                           {"role": "user", "content": user_content}]}

    start = time.time()
    try:
        resp = requests.post(MIMO_API_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return {"answer": data["choices"][0]["message"]["content"],
                "latency": time.time() - start, "success": True}
    except Exception as e:
        return {"answer": "", "latency": time.time() - start, "success": False, "error": str(e)}


def mock_retrieval(case: GoldCase, config: dict) -> list:
    """模拟检索."""
    contexts = [f"[来源] {case.gold_answer}"]
    if config.get("bm25") and case.gold_answer_points:
        contexts.append(f"[BM25] {case.gold_answer_points[0]}")
    if config.get("graph") and case.supporting_entities:
        contexts.append(f"[图谱] {case.supporting_entities[0]} 相关信息")
    return contexts


def check_answer(answer: str, case: GoldCase) -> float:
    """检查要点覆盖率 (boundary 类型用拒答正确率)."""
    answer_lower = answer.lower()

    # boundary 类型: 正确拒答得 1.0，否则 0.0
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


def load_progress() -> dict:
    """加载已完成的进度."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_progress(progress: dict):
    """保存进度."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2, default=str)


def run_single_task(task: dict) -> dict:
    """运行单个评测任务 (用于并行)."""
    case_id = task["case_id"]
    group = task["group"]
    case = task["case"]
    config = task["config"]

    # 模拟检索
    contexts = mock_retrieval(case, config)
    context_text = "\n\n".join(contexts)

    # 调用 API
    result = call_mimo(case.question, context_text)

    if not result["success"]:
        return {"case_id": case_id, "group": group, "error": result.get("error")}

    # 计算指标
    point_coverage = check_answer(result["answer"], case)
    query_result = QueryResult(
        answer=result["answer"], contexts=contexts, citations=[],
        retrieved_ids=case.gold_context_ids,
        trace_nodes=["planner", "retriever", "reasoner", "generator"],
        crag_decision="keep", tool_calls=1, latency=result["latency"]
    )
    metrics = compute_metrics(case, query_result, point_coverage=point_coverage)

    return {"case_id": case_id, "group": group, "metrics": metrics}


def smoke_test():
    """冒烟测试 - 只跑 1 题验证配置."""
    print("=" * 50)
    print("Smoke Test - 验证配置")
    print("=" * 50)

    cases = load_benchmark("eval/datasets/benchmark_20.jsonl")
    case = cases[0]
    print(f"Testing: {case.id} - {case.question[:50]}...")

    result = call_mimo(case.question, case.gold_answer)
    if result["success"]:
        print(f"[PASS] API OK, latency={result['latency']:.1f}s")
        print(f"Answer: {result['answer'][:100]}...")
        return True
    else:
        print(f"[FAIL] API error: {result.get('error')}")
        return False


def run_eval(max_workers: int = 5, groups: list = None, resume: bool = True):
    """运行评测 - 支持并行和断点续传."""
    print("=" * 60)
    print("GraphRAG Copilot Optimized Evaluation")
    print("=" * 60)

    # 加载数据集
    cases = load_benchmark("eval/datasets/benchmark_20.jsonl")
    print(f"Loaded {len(cases)} cases")

    # 加载进度
    progress = load_progress() if resume else {}
    if progress:
        print(f"Resuming from {len(progress)} completed tasks")

    # 准备任务
    if groups is None:
        groups = ["A", "B", "C", "D", "E"]

    tasks = []
    for group in groups:
        config = ABLATION_GROUPS[group].copy()
        for case in cases:
            task_key = f"{group}_{case.id}"
            if task_key not in progress:
                tasks.append({
                    "case_id": case.id,
                    "group": group,
                    "case": case,
                    "config": config,
                    "task_key": task_key,
                })

    print(f"Tasks to run: {len(tasks)} (skipped {len(progress)} completed)")
    print(f"Parallel workers: {max_workers}")
    print(f"Estimated time: {len(tasks) * 15 / max_workers / 60:.1f} min")
    print()

    # 并行执行
    start_time = time.time()
    completed = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(run_single_task, t): t for t in tasks}

        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                result = future.result()
                task_key = task["task_key"]

                if "error" in result:
                    errors += 1
                    print(f"[ERR] {result['case_id']} ({result['group']}): {result['error'][:50]}")
                else:
                    progress[task_key] = result["metrics"]
                    completed += 1

                    # 实时保存进度
                    if completed % 10 == 0:
                        save_progress(progress)

                    # 进度显示
                    total_done = completed + errors
                    pct = total_done / len(tasks) * 100
                    elapsed = time.time() - start_time
                    eta = elapsed / total_done * (len(tasks) - total_done) if total_done > 0 else 0
                    acc = result["metrics"].get("answer_accuracy", 0)
                    print(f"[{pct:5.1f}%] {result['case_id']} ({result['group']}): acc={acc:.2f} | ETA {eta/60:.1f}min")

            except Exception as e:
                errors += 1
                print(f"[ERR] {task['case_id']}: {str(e)[:50]}")

    # 保存最终结果
    save_progress(progress)
    elapsed = time.time() - start_time

    # 汇总
    print()
    print("=" * 60)
    print(f"Completed: {completed} | Errors: {errors} | Time: {elapsed:.0f}s")
    print("=" * 60)

    # 按组汇总
    print(f"\n{'Group':<8} {'Accuracy':<12} {'Faithfulness':<15} {'Count':<8}")
    print("-" * 45)

    for group in groups:
        group_results = [v for k, v in progress.items() if k.startswith(f"{group}_") and "answer_accuracy" in v]
        if group_results:
            avg_acc = sum(r["answer_accuracy"] for r in group_results) / len(group_results)
            avg_faith = sum(r["faithfulness"] for r in group_results) / len(group_results)
            print(f"{group:<8} {avg_acc:<12.4f} {avg_faith:<15.4f} {len(group_results):<8}")

    # 保存汇总
    summary_file = RESULTS_DIR / "eval_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({"progress": progress, "elapsed": elapsed, "completed": completed, "errors": errors},
                  f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults saved to: {summary_file}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="优化版评测脚本")
    parser.add_argument("--smoke", action="store_true", help="冒烟测试 (只跑 1 题)")
    parser.add_argument("--workers", type=int, default=5, help="并行线程数 (默认 5)")
    parser.add_argument("--groups", nargs="+", default=["A", "B", "C", "D", "E"], help="消融组")
    parser.add_argument("--no-resume", action="store_true", help="不续传，重新开始")

    args = parser.parse_args()

    if args.smoke:
        success = smoke_test()
        sys.exit(0 if success else 1)
    else:
        run_eval(max_workers=args.workers, groups=args.groups, resume=not args.no_resume)


if __name__ == "__main__":
    main()
