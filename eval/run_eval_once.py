"""一次性评测脚本 — 避免 hermes-agent 干扰."""
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.graphrag_client import run_query
from eval.datasets import load_benchmark
from eval.metrics import compute_metrics
from eval.tests.run_real_eval import check_answer

def main():
    base_url = "http://localhost:8000"
    cases = load_benchmark("eval/datasets/benchmark_50.jsonl")
    print(f"Loaded {len(cases)} cases, base_url={base_url}")

    results = []
    errors = 0
    start = time.time()

    for i, case in enumerate(cases):
        for attempt in range(3):
            try:
                result = run_query(case.question, {"vector": True, "bm25": True, "graph": True}, base_url=base_url)
                pc = check_answer(result.answer, case)
                metrics = compute_metrics(case, result, point_coverage=pc, use_llm=False)
                status = "OK" if pc > 0 else "MISS"
                print(f"[{i+1}/{len(cases)}] {status} {case.id} ({case.type}): acc={pc:.2f} faith={metrics.get('faithfulness',0):.2f} lat={result.latency:.1f}s", flush=True)
                results.append(metrics)
                break
            except Exception as e:
                if attempt < 2:
                    wait = 10 * (attempt + 1)
                    print(f"[{i+1}/{len(cases)}] {case.id} attempt {attempt+1} failed, retry in {wait}s: {e}", flush=True)
                    time.sleep(wait)
                else:
                    errors += 1
                    print(f"[{i+1}/{len(cases)}] ERR {case.id}: {e}", flush=True)

    elapsed = time.time() - start
    print(f"\nCompleted: {len(results)} | Errors: {errors} | Time: {elapsed:.0f}s")

    if not results:
        print("No results!")
        return

    # Summary
    for key in ["answer_accuracy", "faithfulness", "hallucination_rate", "boundary_refusal_rate"]:
        vals = [r[key] for r in results if key in r]
        if vals:
            print(f"{key}: {sum(vals)/len(vals):.4f}")

    # By type
    print(f"\n{'Type':<12} {'Accuracy':<12} {'Faithfulness':<15} {'Count'}")
    print("-" * 50)
    for qtype in ["factual", "relational", "multihop", "crossdoc", "boundary"]:
        tr = [r for r in results if r.get("case_type") == qtype]
        if tr:
            aa = sum(r["answer_accuracy"] for r in tr) / len(tr)
            af = sum(r["faithfulness"] for r in tr) / len(tr)
            print(f"{qtype:<12} {aa:<12.4f} {af:<15.4f} {len(tr)}")

    # Save
    out = Path("eval/results/real_eval_final.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "base_url": base_url,
            "n_cases": len(results),
            "elapsed": elapsed,
            "results": results,
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults saved to: {out}")

if __name__ == "__main__":
    main()
