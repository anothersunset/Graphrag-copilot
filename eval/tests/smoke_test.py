"""精简烟雾测试 — 验证核心功能是否正常.

用法: python eval/tests/smoke_test.py
日志输出到 eval/results/smoke_test.log
"""
import json
import sys
import time
import logging
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

# ── 日志配置 ──
LOG_DIR = Path(__file__).parent.parent / "results"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "smoke_test.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("smoke_test")

BASE = "http://localhost:8000"
TIMEOUT = 120

# ── 测试用例（每类 1 题）──
CASES = [
    {
        "id": "factual-001",
        "query": "系统使用什么向量数据库？",
        "type": "factual",
        "min_answer_len": 20,
        "must_contain_any": [["FAISS"], ["faiss"]],
    },
    {
        "id": "relational-001",
        "query": "证据融合服务如何处理不同检索源的结果？",
        "type": "relational",
        "min_answer_len": 30,
        "must_contain_any": [["融合", "fuse"], ["vector", "bm25", "graph"], ["向量", "BM25", "图谱"]],
    },
    {
        "id": "multihop-001",
        "query": "从文档上传到可被检索的完整流程是什么？",
        "type": "multihop",
        "min_answer_len": 30,
        "must_contain_any": [["上传", "parse"], ["分块", "chunk"], ["向量", "embed"]],
    },
]


def call_api(query: str) -> dict:
    body = json.dumps({"query": query}).encode("utf-8")
    req = Request(f"{BASE}/api/query", data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def check_answer(answer: str, case: dict) -> bool:
    # 答案长度检查
    min_len = case.get("min_answer_len", 10)
    if len(answer.strip()) < min_len:
        return False
    answer_lower = answer.lower()
    # must_contain_any: 至少一组关键词全部出现
    for group in case.get("must_contain_any", []):
        if all(kw.lower() in answer_lower for kw in group):
            return True
    return False


def main():
    log.info("=" * 60)
    log.info("GraphRAG Copilot 烟雾测试开始")
    log.info("=" * 60)

    # 健康检查
    try:
        health = urlopen(f"{BASE}/health", timeout=10).read().decode()
        log.info("健康检查: %s", health)
    except Exception as e:
        log.error("后端未启动: %s", e)
        sys.exit(1)

    passed = 0
    failed = 0

    for case in CASES:
        log.info("-" * 40)
        log.info("[%s] %s", case["id"], case["query"])
        t0 = time.time()

        try:
            result = call_api(case["query"])
            elapsed = time.time() - t0
            answer = result.get("answer", "")
            confidence = result.get("confidence", 0.0)
            crag = result.get("crag_decision", "?")
            nodes = result.get("trace", {}).get("nodes", [])

            ok = check_answer(answer, case)
            status = "PASS" if ok else "FAIL"

            log.info("  耗时: %.1fs", elapsed)
            log.info("  置信度: %.2f | CRAG: %s", confidence, crag)
            log.info("  节点: %s", nodes)
            log.info("  答案: %s", answer[:200])
            log.info("  结果: %s", status)

            if ok:
                passed += 1
            else:
                failed += 1
                log.warning("  关键词检查失败")

        except Exception as e:
            elapsed = time.time() - t0
            log.error("  异常 (%.1fs): %s", elapsed, e)
            failed += 1

    log.info("=" * 60)
    log.info("结果: %d/%d 通过", passed, passed + failed)
    log.info("日志: %s", LOG_FILE)
    log.info("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
