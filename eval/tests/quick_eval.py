"""快速评测脚本 - 测试优化效果"""

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

# 选择代表性用例（每种类型至少 2 个）
test_cases = [
    # factual
    next(c for c in cases if c["id"] == "kb-factual-001"),
    next(c for c in cases if c["id"] == "kb-factual-007"),
    next(c for c in cases if c["id"] == "kb-factual-004"),
    # relational
    next(c for c in cases if c["id"] == "kb-relational-001"),
    next(c for c in cases if c["id"] == "kb-relational-003"),
    # multihop
    next(c for c in cases if c["id"] == "kb-multihop-001"),
    next(c for c in cases if c["id"] == "kb-multihop-004"),
    next(c for c in cases if c["id"] == "kb-multihop-011"),
    # boundary（现在 kb-boundary-001 是可回答的）
    next(c for c in cases if c["id"] == "kb-boundary-001"),
    next(c for c in cases if c["id"] == "kb-boundary-002"),
]


def check_answer(answer: str, case: dict) -> float:
    """检查要点覆盖率 — 使用宽松的子串匹配"""
    answer_lower = answer.lower()
    points = case.get("gold_answer_points", [])

    if not points:
        return 0.0

    if case["type"] == "boundary" and not case.get("expect_answerable", True):
        # boundary 且不可回答：检查是否拒答
        refusal_keywords = [
            "没有找到", "无法回答", "信息不足", "不确定", "不知道",
            "没有相关信息", "知识库中没有", "未提供", "未找到",
            "无法确定", "无法提供", "缺少信息", "没有足够",
            "不详", "不足", "无法给出",
        ]
        return 1.0 if any(kw in answer_lower for kw in refusal_keywords) else 0.0

    # 对每个要点：如果整个关键词出现在答案中（不区分大小写），算命中
    # 对于较长的关键词（>6字符），也接受子串匹配
    covered = 0
    for point in points:
        point_lower = point.lower()
        if point_lower in answer_lower:
            covered += 1
        elif len(point_lower) > 6:
            # 长关键词：检查是否有 6 字符子串匹配
            matched = any(
                point_lower[i:i+6] in answer_lower
                for i in range(0, len(point_lower) - 5, 3)
            )
            if matched:
                covered += 1
        elif len(point_lower) >= 3:
            # 中等关键词：直接子串匹配
            if point_lower in answer_lower:
                covered += 1

    return covered / len(points)


def check_citation(answer: str) -> bool:
    """检查是否有引用标记"""
    markers = ["[chunk:", "[1]", "[2]", "[3]", "【", "来源", "参考"]
    return any(m in answer for m in markers)


print("=" * 60)
print("快速评测 - 验证优化效果")
print("=" * 60)

results = []
for i, case in enumerate(test_cases):
    print(f"\n[{i+1}/{len(test_cases)}] {case['id']} ({case['type']})")
    print(f"问题: {case['question'][:60]}...")

    try:
        start = time.time()
        response = requests.post(
            "http://localhost:8000/api/query",
            json={"query": case["question"]},
            timeout=300,
        )
        latency = time.time() - start

        if response.status_code != 200:
            print(f"  HTTP {response.status_code}: {response.text[:100]}")
            results.append({
                "case_id": case["id"], "type": case["type"],
                "error": f"HTTP {response.status_code}",
            })
            continue

        result = response.json()
        answer = result.get("answer", "")
        accuracy = check_answer(answer, case)
        has_citation = check_citation(answer)

        status = "OK" if accuracy > 0 else "MISS"
        print(f"  {status} accuracy={accuracy:.2f} citation={has_citation} latency={latency:.1f}s len={len(answer)}")
        print(f"  答案: {answer[:120]}...")

        results.append({
            "case_id": case["id"],
            "type": case["type"],
            "accuracy": accuracy,
            "has_citation": has_citation,
            "latency": latency,
            "answer_len": len(answer),
        })

    except Exception as e:
        print(f"  ERR: {type(e).__name__}: {e}")
        results.append({
            "case_id": case["id"], "type": case["type"],
            "error": str(e),
        })

# 汇总
print("\n" + "=" * 60)
print("汇总结果")
print("=" * 60)

valid_results = [r for r in results if "error" not in r]
if valid_results:
    avg_accuracy = sum(r["accuracy"] for r in valid_results) / len(valid_results)
    citation_rate = sum(1 for r in valid_results if r["has_citation"]) / len(valid_results)
    avg_latency = sum(r["latency"] for r in valid_results) / len(valid_results)

    print(f"平均 Accuracy: {avg_accuracy:.4f}")
    print(f"引用率: {citation_rate:.4f}")
    print(f"平均延迟: {avg_latency:.2f}s")

    # 按类型统计
    for qtype in ["factual", "relational", "multihop", "boundary", "crossdoc"]:
        type_results = [r for r in valid_results if r["type"] == qtype]
        if type_results:
            type_acc = sum(r["accuracy"] for r in type_results) / len(type_results)
            print(f"  {qtype}: accuracy={type_acc:.4f} (n={len(type_results)})")

# 保存结果
out_file = Path("eval/results/quick_eval_results.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "summary": {
            "avg_accuracy": avg_accuracy if valid_results else 0,
            "citation_rate": citation_rate if valid_results else 0,
            "avg_latency": avg_latency if valid_results else 0,
        }
    }, f, ensure_ascii=False, indent=2)
print(f"\n结果已保存到: {out_file}")
