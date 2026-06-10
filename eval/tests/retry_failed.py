"""重试失败的评测用例"""

import json
import time
import requests
from pathlib import Path

# 加载 benchmark
benchmark_file = Path("eval/datasets/benchmark_50.jsonl")
cases = []
with open(benchmark_file, encoding="utf-8") as f:
    for line in f:
        if line.strip():
            cases.append(json.loads(line))

# 加载已有结果
results_file = Path("eval/results/quick_eval_results.json")
with open(results_file, encoding="utf-8") as f:
    existing = json.load(f)

existing_ids = {r["case_id"] for r in existing["results"] if "error" not in r}
failed_ids = [r["case_id"] for r in existing["results"] if "error" in r]

print(f"已有成功结果: {len(existing_ids)}")
print(f"需要重试: {len(failed_ids)}")
print(f"失败用例: {failed_ids}")

# 找到需要重试的用例
retry_cases = [c for c in cases if c["id"] in failed_ids]


def check_answer(answer: str, case: dict) -> float:
    answer_lower = answer.lower()
    points = case.get("gold_answer_points", [])
    if not points:
        return 0.0
    if case["type"] == "boundary" and not case.get("expect_answerable", True):
        refusal_keywords = [
            "没有找到", "无法回答", "信息不足", "不确定", "不知道",
            "没有相关信息", "知识库中没有", "未提供", "未找到",
            "无法确定", "无法提供", "缺少信息", "没有足够", "不详", "不足",
        ]
        return 1.0 if any(kw in answer_lower for kw in refusal_keywords) else 0.0

    covered = 0
    for point in points:
        point_lower = point.lower()
        if point_lower in answer_lower:
            covered += 1
        elif len(point_lower) > 6:
            matched = any(
                point_lower[i:i+6] in answer_lower
                for i in range(0, len(point_lower) - 5, 3)
            )
            if matched:
                covered += 1
    return covered / len(points)


def check_citation(answer: str) -> bool:
    markers = ["[chunk:", "[1]", "[2]", "[3]", "【", "来源", "参考"]
    return any(m in answer for m in markers)


new_results = []
for i, case in enumerate(retry_cases):
    print(f"\n[{i+1}/{len(retry_cases)}] {case['id']} ({case['type']})")

    try:
        start = time.time()
        response = requests.post(
            "http://localhost:8000/api/query",
            json={"query": case["question"]},
            timeout=600,
        )
        latency = time.time() - start

        if response.status_code != 200:
            print(f"  HTTP {response.status_code}")
            new_results.append({"case_id": case["id"], "type": case["type"], "error": f"HTTP {response.status_code}"})
            continue

        result = response.json()
        answer = result.get("answer", "")
        accuracy = check_answer(answer, case)
        has_citation = check_citation(answer)

        print(f"  {'OK' if accuracy > 0 else 'MISS'} accuracy={accuracy:.2f} latency={latency:.1f}s len={len(answer)}")
        new_results.append({
            "case_id": case["id"], "type": case["type"],
            "accuracy": accuracy, "has_citation": has_citation,
            "latency": latency, "answer_len": len(answer),
        })
    except Exception as e:
        print(f"  ERR: {type(e).__name__}: {e}")
        new_results.append({"case_id": case["id"], "type": case["type"], "error": str(e)})

# 合并结果
all_results = [r for r in existing["results"] if "error" not in r] + new_results
valid = [r for r in all_results if "error" not in r]

if valid:
    avg_acc = sum(r["accuracy"] for r in valid) / len(valid)
    cit_rate = sum(1 for r in valid if r["has_citation"]) / len(valid)
    avg_lat = sum(r["latency"] for r in valid) / len(valid)

    print(f"\n{'='*60}")
    print(f"合并结果: {len(valid)}/10 成功")
    print(f"平均 Accuracy: {avg_acc:.4f}")
    print(f"引用率: {cit_rate:.4f}")
    print(f"平均延迟: {avg_lat:.2f}s")

    for qtype in ["factual", "relational", "multihop", "boundary"]:
        type_results = [r for r in valid if r["type"] == qtype]
        if type_results:
            type_acc = sum(r["accuracy"] for r in type_results) / len(type_results)
            print(f"  {qtype}: accuracy={type_acc:.4f} (n={len(type_results)})")

# 保存合并结果
out_file = Path("eval/results/quick_eval_results.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": all_results,
        "summary": {
            "avg_accuracy": avg_acc if valid else 0,
            "citation_rate": cit_rate if valid else 0,
            "avg_latency": avg_lat if valid else 0,
        }
    }, f, ensure_ascii=False, indent=2)
print(f"\n结果已保存到: {out_file}")
