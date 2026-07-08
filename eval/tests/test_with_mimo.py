"""直接调用 mimo API 测试 eval 脚手架 - 不依赖后端服务."""
import json
import sys
import time
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


def call_mimo(question: str, context: str = "") -> dict:
    """直接调用 mimo API."""
    system_prompt = (
        "你是严谨的企业知识问答助手。必须基于给定上下文回答。\n"
        "要求:\n"
        "1. 只基于上下文回答，不允许编造。\n"
        "2. 每个关键结论尽量标注来源编号。\n"
        "3. 如果证据不足，明确说明不足。\n"
        "输出 JSON: {\"answer\": \"回答\", \"points_covered\": [], \"confidence\": 0.0}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"问题: {question}\n\n上下文:\n{context}" if context else f"问题: {question}"},
    ]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MIMO_API_KEY}",
    }
    payload = {
        "model": MIMO_MODEL,
        "max_tokens": 1000,
        "messages": messages,
    }

    start = time.time()
    try:
        resp = requests.post(MIMO_API_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        latency = time.time() - start

        content = data["choices"][0]["message"]["content"]
        reasoning = data["choices"][0]["message"].get("reasoning_content", "")

        return {
            "answer": content,
            "reasoning": reasoning,
            "latency": latency,
            "success": True,
        }
    except Exception as e:
        return {
            "answer": "",
            "reasoning": "",
            "latency": time.time() - start,
            "success": False,
            "error": str(e),
        }


def mock_retrieval(question: str, case: GoldCase) -> list:
    """模拟检索结果 - 返回 gold_context_ids 对应的假内容."""
    # 简化: 返回问题相关的假上下文
    entity = case.supporting_entities[0] if case.supporting_entities else "系统"
    point = case.gold_answer_points[0] if case.gold_answer_points else "相关信息"
    return [
        f"[Context 1] 关于 {entity} 的信息: {case.gold_answer[:100]}...",
        f"[Context 2] {point}...",
    ]


def test_single_case(case: GoldCase) -> dict:
    """测试单个用例."""
    print(f"\n  Testing: {case.id} ({case.type}/{case.difficulty})")
    print(f"  Q: {case.question[:60]}...")

    # 模拟检索
    contexts = mock_retrieval(case.question, case)

    # 调用 mimo
    result = call_mimo(case.question, "\n\n".join(contexts))

    if not result["success"]:
        print(f"  [FAIL] API error: {result.get('error')}")
        return {"case_id": case.id, "error": result.get("error")}

    print(f"  A: {result['answer'][:80]}...")
    print(f"  Latency: {result['latency']:.2f}s")

    # 构造 QueryResult
    query_result = QueryResult(
        answer=result["answer"],
        contexts=contexts,
        citations=[],
        retrieved_ids=case.gold_context_ids,
        trace_nodes=["planner", "retriever", "reasoner", "generator"],  # 模拟
        crag_decision="keep",
        tool_calls=1,
        latency=result["latency"],
    )

    # 计算指标 (point_coverage 简化为关键词匹配)
    answer_lower = result["answer"].lower()
    covered = sum(1 for p in case.gold_answer_points if p.lower() in answer_lower)
    point_coverage = covered / len(case.gold_answer_points) if case.gold_answer_points else 0.0

    metrics = compute_metrics(case, query_result, point_coverage=point_coverage)
    print(f"  Metrics: recall={metrics['recall_at_5']:.2f}, accuracy={metrics['answer_accuracy']:.2f}, faithfulness={metrics['faithfulness']:.2f}")

    return metrics


def main():
    """运行测试."""
    print("=" * 60)
    print("Eval Scaffold + mimo-v2.5-pro Integration Test")
    print("=" * 60)

    # 加载数据集
    print("\n[1] Loading benchmark...")
    cases = load_benchmark("eval/datasets/seed_benchmark.jsonl")
    print(f"    Loaded {len(cases)} cases")

    # 测试前 3 个用例 (节省 token)
    test_cases = cases[:3]
    print(f"\n[2] Testing {len(test_cases)} cases with mimo...")

    results = []
    for case in test_cases:
        metrics = test_single_case(case)
        results.append(metrics)

    # 汇总
    print("\n" + "=" * 60)
    print("[3] Summary")
    print("=" * 60)

    valid_results = [r for r in results if "error" not in r]
    if valid_results:
        avg_recall = sum(r["recall_at_5"] for r in valid_results) / len(valid_results)
        avg_accuracy = sum(r["answer_accuracy"] for r in valid_results) / len(valid_results)
        avg_faithfulness = sum(r["faithfulness"] for r in valid_results) / len(valid_results)
        avg_latency = sum(r["latency"] for r in valid_results) / len(valid_results)

        print(f"  Cases tested: {len(valid_results)}/{len(test_cases)}")
        print(f"  Avg Recall@5: {avg_recall:.4f}")
        print(f"  Avg Answer Accuracy: {avg_accuracy:.4f}")
        print(f"  Avg Faithfulness: {avg_faithfulness:.4f}")
        print(f"  Avg Latency: {avg_latency:.2f}s")
    else:
        print("  No valid results")

    # 保存结果
    out_file = Path("eval/results/mimo_test_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "model": MIMO_MODEL,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "n_cases": len(test_cases),
            "results": results,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  Results saved to: {out_file}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
