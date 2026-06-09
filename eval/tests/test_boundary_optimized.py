"""测试优化后的 boundary 拒答能力."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eval.graphrag_client import GoldCase, QueryResult
from eval.datasets import load_benchmark
from eval.metrics import compute_metrics

import requests

MIMO_API_URL = "https://token-plan-sgp.xiaomimimo.com/v1/chat/completions"
MIMO_API_KEY = "tp-srs1nhj8slfztozf8wac0q7jqmbymynt8p5axo22h42z1u0u"
MIMO_MODEL = "mimo-v2.5-pro"


# 优化后的 prompt - 强调拒答
SYSTEM_PROMPT_OPTIMIZED = """你是企业知识问答助手。请严格遵循以下规则：

## 核心规则
1. **只基于上下文回答**：答案必须完全来自提供的上下文
2. **信息不足时必须拒答**：如果上下文没有足够信息，必须明确说"当前知识库中没有找到相关信息"
3. **不要猜测**：不确定的内容不要编造

## 边界问题识别
当问题涉及以下情况时，必须拒答：
- 问题超出知识库范围
- 上下文没有直接相关信息
- 需要实时数据（如性能指标、覆盖率、QPS 等）
- 需要未提供的配置细节
- 涉及具体的数字、统计数据

## 回答格式
- 如果能回答：直接回答，简洁明了
- 如果不能回答：说"当前知识库中没有找到相关信息"，然后说明原因

请回答以下问题："""


SYSTEM_PROMPT_BASIC = """你是企业知识问答助手。请基于上下文回答问题。
1. 只基于上下文回答，不要编造
2. 信息不足时说"当前知识库中没有找到相关信息"
3. 简洁明了，不超过200字"""


def call_mimo(question: str, context: str, use_optimized_prompt: bool = False) -> dict:
    """调用 mimo API."""
    system_prompt = SYSTEM_PROMPT_OPTIMIZED if use_optimized_prompt else SYSTEM_PROMPT_BASIC
    user_content = f"上下文:\n{context}\n\n问题: {question}" if context else f"问题: {question}"

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {MIMO_API_KEY}"}
    payload = {
        "model": MIMO_MODEL,
        "max_tokens": 800,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
    }

    start = time.time()
    try:
        resp = requests.post(MIMO_API_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return {
            "answer": data["choices"][0]["message"]["content"],
            "latency": time.time() - start,
            "success": True
        }
    except Exception as e:
        return {"answer": "", "latency": time.time() - start, "success": False, "error": str(e)}


def check_boundary_refusal(answer: str) -> bool:
    """检查是否正确拒答."""
    refusal_keywords = [
        "没有找到", "无法回答", "信息不足", "不确定", "不知道",
        "没有相关信息", "知识库中没有", "未提供", "未找到",
        "无法确定", "无法提供", "缺少信息", "没有足够"
    ]
    answer_lower = answer.lower()
    return any(kw in answer_lower for kw in refusal_keywords)


def mock_retrieval(case: GoldCase) -> list:
    """模拟检索 - 对 boundary 用例返回空上下文."""
    # boundary 用例不应该有相关上下文
    return ["[上下文] 无相关信息"]


def test_boundary_cases(use_optimized_prompt: bool = False):
    """测试 boundary 用例."""
    cases = load_benchmark('eval/datasets/benchmark_50.jsonl')
    boundary_cases = [c for c in cases if c.type == 'boundary']

    prompt_type = "优化版" if use_optimized_prompt else "基础版"
    print(f"\n{'='*70}")
    print(f"Boundary 拒答测试 ({prompt_type} Prompt)")
    print(f"{'='*70}")

    results = []
    for case in boundary_cases:
        contexts = mock_retrieval(case)
        result = call_mimo(case.question, '\n\n'.join(contexts), use_optimized_prompt)

        if not result['success']:
            print(f"[ERR] {case.id}: {result.get('error')}")
            continue

        is_refusal = check_boundary_refusal(result['answer'])
        status = "PASS" if is_refusal else "FAIL"

        print(f"\n[{status}] {case.id}")
        print(f"  Q: {case.question[:60]}...")
        print(f"  A: {result['answer'][:100]}...")
        print(f"  拒答: {is_refusal}")

        results.append({
            "case_id": case.id,
            "is_refusal": is_refusal,
            "answer": result['answer'],
            "latency": result['latency']
        })

    # 统计
    total = len(results)
    refused = sum(1 for r in results if r['is_refusal'])
    refusal_rate = refused / total if total > 0 else 0

    print(f"\n{'='*70}")
    print(f"结果: {refused}/{total} 正确拒答 ({refusal_rate:.2%})")
    print(f"{'='*70}")

    return results


def main():
    """对比测试."""
    # 测试基础版 prompt
    basic_results = test_boundary_cases(use_optimized_prompt=False)

    # 测试优化版 prompt
    optimized_results = test_boundary_cases(use_optimized_prompt=True)

    # 对比
    basic_refusal = sum(1 for r in basic_results if r['is_refusal'])
    opt_refusal = sum(1 for r in optimized_results if r['is_refusal'])

    print(f"\n{'='*70}")
    print("对比结果")
    print(f"{'='*70}")
    print(f"基础版 Prompt: {basic_refusal}/{len(basic_results)} 拒答")
    print(f"优化版 Prompt: {opt_refusal}/{len(optimized_results)} 拒答")
    print(f"提升: {opt_refusal - basic_refusal} 个用例")


if __name__ == "__main__":
    main()
