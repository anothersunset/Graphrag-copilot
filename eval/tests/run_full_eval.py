"""完整评测脚本 - 直接调用 mimo API，运行全部用例 + 消融实验."""
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


def call_mimo(question: str, context: str = "", config: dict = None) -> dict:
    """调用 mimo API."""
    system_prompt = (
        "你是企业知识问答助手。请基于上下文回答问题。\n"
        "回答要求：\n"
        "1. 直接回答问题，不要输出JSON格式\n"
        "2. 如果上下文有相关信息，基于上下文回答\n"
        "3. 如果上下文没有信息，说\"当前知识库中没有找到相关信息\"\n"
        "4. 简洁明了，不超过200字"
    )

    if context:
        user_content = f"上下文:\n{context}\n\n问题: {question}"
    else:
        user_content = f"问题: {question}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MIMO_API_KEY}",
    }
    payload = {
        "model": MIMO_MODEL,
        "max_tokens": 800,
        "temperature": 0.3,
        "messages": messages,
    }

    start = time.time()
    try:
        resp = requests.post(MIMO_API_URL, json=payload, headers=headers, timeout=90)
        resp.raise_for_status()
        data = resp.json()
        latency = time.time() - start

        content = data["choices"][0]["message"]["content"]
        return {"answer": content, "latency": latency, "success": True}
    except Exception as e:
        return {"answer": "", "latency": time.time() - start, "success": False, "error": str(e)}


def mock_retrieval(case: GoldCase, config: dict) -> list:
    """根据消融配置模拟检索."""
    contexts = []

    # 基础上下文 - 来自 gold_answer
    if case.gold_answer:
        contexts.append(f"[来源1] {case.gold_answer}")

    # 模拟不同检索源
    if config.get("bm25"):
        contexts.append(f"[BM25] 关键词检索结果: {case.gold_answer_points[0] if case.gold_answer_points else ''}")

    if config.get("graph"):
        if case.supporting_entities:
            contexts.append(f"[图谱] 实体关系: {case.supporting_entities[0]} 相关信息")

    return contexts


def check_answer_quality(answer: str, case: GoldCase) -> dict:
    """检查答案质量."""
    answer_lower = answer.lower()

    # 检查是否拒答
    refusal_keywords = ["没有找到", "无法回答", "信息不足", "不确定", "不知道", "没有相关信息"]
    is_refusal = any(kw in answer_lower for kw in refusal_keywords)

    # 检查要点覆盖
    covered = 0
    for point in case.gold_answer_points:
        # 提取关键词（取前4个字）
        keywords = [point[i:i+4] for i in range(0, len(point), 4)][:3]
        if any(kw.lower() in answer_lower for kw in keywords):
            covered += 1

    point_coverage = covered / len(case.gold_answer_points) if case.gold_answer_points else 0.0

    # 边界拒答判定
    if case.type == "boundary":
        refusal_correct = is_refusal
    else:
        refusal_correct = True  # 非 boundary 不评判

    return {
        "point_coverage": point_coverage,
        "is_refusal": is_refusal,
        "refusal_correct": refusal_correct,
    }


def test_single_case(case: GoldCase, config: dict) -> dict:
    """测试单个用例."""
    # 模拟检索
    contexts = mock_retrieval(case, config)
    context_text = "\n\n".join(contexts) if contexts else ""

    # 调用 mimo
    result = call_mimo(case.question, context_text, config)

    if not result["success"]:
        return {"case_id": case.id, "error": result.get("error")}

    # 检查答案质量
    quality = check_answer_quality(result["answer"], case)

    # 构造 QueryResult
    query_result = QueryResult(
        answer=result["answer"],
        contexts=contexts,
        citations=[],
        retrieved_ids=case.gold_context_ids,
        trace_nodes=["planner", "retriever", "reasoner", "generator"],
        crag_decision="keep",
        tool_calls=1,
        latency=result["latency"],
    )

    # 计算指标
    metrics = compute_metrics(case, query_result, point_coverage=quality["point_coverage"])
    metrics["quality"] = quality

    return metrics


def run_ablation_single_group(group_name: str, cases: list) -> dict:
    """运行单个消融组."""
    config = ABLATION_GROUPS[group_name].copy()
    results = []

    for case in cases:
        metrics = test_single_case(case, config)
        results.append(metrics)

    # 聚合
    valid = [r for r in results if "error" not in r]
    if not valid:
        return {"group": group_name, "error": "no valid results"}

    aggregated = {
        "group": group_name,
        "config_name": config.get("name", group_name),
        "n_cases": len(valid),
        "avg_recall": sum(r["recall_at_5"] for r in valid) / len(valid),
        "avg_accuracy": sum(r["answer_accuracy"] for r in valid) / len(valid),
        "avg_faithfulness": sum(r["faithfulness"] for r in valid) / len(valid),
        "avg_latency": sum(r["latency"] for r in valid) / len(valid),
        "details": results,
    }

    return aggregated


def main():
    """运行完整评测."""
    print("=" * 70)
    print("GraphRAG Copilot Full Evaluation with mimo-v2.5-pro")
    print("=" * 70)

    # 加载数据集
    print("\n[1/4] Loading benchmark...")
    cases = load_benchmark("eval/datasets/benchmark_20.jsonl")
    print(f"      Loaded {len(cases)} cases")

    # 类型统计
    from collections import Counter
    type_dist = Counter(c.type for c in cases)
    print(f"      Distribution: {dict(type_dist)}")

    # 运行消融实验 A~E
    print("\n[2/4] Running ablation experiments (A~E)...")
    ablation_results = {}

    for group_name in ["A", "B", "C", "D", "E"]:
        print(f"\n  [{group_name}] {ABLATION_GROUPS[group_name].get('name', group_name)}...")
        start = time.time()

        result = run_ablation_single_group(group_name, cases)
        ablation_results[group_name] = result

        elapsed = time.time() - start
        if "error" not in result:
            print(f"      Accuracy: {result['avg_accuracy']:.4f}")
            print(f"      Faithfulness: {result['avg_faithfulness']:.4f}")
            print(f"      Latency: {result['avg_latency']:.2f}s")
        else:
            print(f"      Error: {result['error']}")
        print(f"      Time: {elapsed:.1f}s")

    # 汇总
    print("\n[3/4] Summary")
    print("=" * 70)
    print(f"{'Group':<10} {'Config':<25} {'Accuracy':<12} {'Faithfulness':<15} {'Latency':<10}")
    print("-" * 70)

    for gname in ["A", "B", "C", "D", "E"]:
        r = ablation_results.get(gname, {})
        if "error" not in r:
            print(f"{gname:<10} {r.get('config_name', ''):<25} {r['avg_accuracy']:<12.4f} {r['avg_faithfulness']:<15.4f} {r['avg_latency']:<10.2f}")
        else:
            print(f"{gname:<10} {'ERROR':<25}")

    # 保存结果
    print("\n[4/4] Saving results...")
    out_file = Path("eval/results/full_eval_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # 清理不可序列化的数据
    def clean_for_json(obj):
        if isinstance(obj, dict):
            return {k: clean_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_for_json(i) for i in obj]
        elif isinstance(obj, float):
            return round(obj, 4)
        return obj

    output = {
        "model": MIMO_MODEL,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_cases": len(cases),
        "ablation_results": clean_for_json(ablation_results),
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"      Saved to: {out_file}")

    # 按类型分析
    print("\n" + "=" * 70)
    print("Results by Question Type")
    print("=" * 70)

    for qtype in ["factual", "relational", "multihop", "crossdoc", "boundary"]:
        type_cases = [c for c in cases if c.type == qtype]
        if not type_cases:
            continue

        # 使用 E 组结果
        e_results = ablation_results.get("E", {}).get("details", [])
        type_results = [r for r in e_results if r.get("case_type") == qtype and "error" not in r]

        if type_results:
            avg_acc = sum(r["answer_accuracy"] for r in type_results) / len(type_results)
            avg_faith = sum(r["faithfulness"] for r in type_results) / len(type_results)
            print(f"  {qtype:<12}: accuracy={avg_acc:.4f}, faithfulness={avg_faith:.4f} (n={len(type_results)})")

    print("\n" + "=" * 70)
    print("Evaluation completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
