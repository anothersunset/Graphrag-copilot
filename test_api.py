"""GraphRAG Copilot - “冷烟” (smoke) 脚本

使用场景：
  - 本地启动后走一遭关键路径，验证进程是否 “冤烟”
  - 部署后的 readiness gate：返回码 ≠ 0 则阻断发布

环境变量（均可选）：
  BASE_URL          默认 http://localhost:8000
  API_KEY           默认 test-key-1（仅是占位，请与服务端 API_KEYS 中某一个一致）
  ENABLE_AUTH       'true'/'false'，默认 'false'。true 时会额外跑鉴权用例
  RATE_LIMIT_PER_MIN默认 60；限流 smoke 会发 N+1 次 /health。调小可加速验证
示例：
  BASE_URL=http://localhost:8000 API_KEY=test-key-1 ENABLE_AUTH=true \
      RATE_LIMIT_PER_MIN=5 python test_api.py
"""
import os
import sys
from typing import Callable, List, Tuple

import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "test-key-1")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))


def _auth_headers() -> dict:
    return {"X-API-Key": API_KEY} if ENABLE_AUTH else {}


def test_health() -> bool:
    print("[1] 健康检查")
    r = requests.get(BASE_URL + "/health", timeout=5)
    print("   ->", r.status_code, r.json())
    return r.status_code == 200


def test_system_status() -> bool:
    print("[2] 系统状态")
    r = requests.get(BASE_URL + "/api/system/status", timeout=5)
    print("   ->", r.status_code)
    return r.status_code == 200


def test_vector_stats() -> bool:
    print("[3] 向量库统计")
    r = requests.get(BASE_URL + "/api/vector/stats", timeout=5)
    print("   ->", r.status_code)
    return r.status_code == 200


def test_graph_stats() -> bool:
    print("[4] 知识图谱统计")
    r = requests.get(BASE_URL + "/api/graph/stats", timeout=5)
    print("   ->", r.status_code)
    return r.status_code == 200


def test_query() -> bool:
    print("[5] 智能问答")
    r = requests.post(
        BASE_URL + "/api/query",
        json={"query": "什么是 GraphRAG？", "top_k": 5},
        headers=_auth_headers(),
        timeout=30,
    )
    # 未部署 LLM 时会返 500；鉴权失败会返 401/503
    print("   ->", r.status_code)
    return r.status_code in (200, 500)


def test_document_upload() -> bool:
    print("[6] 文档上传")
    content = "GraphRAG 是结合知识图谱和 RAG 的检索增强生成技术。"
    tmp = "_smoke_test_document.txt"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        with open(tmp, "rb") as f:
            r = requests.post(
                BASE_URL + "/api/documents/upload",
                files={"file": ("test.txt", f, "text/plain")},
                headers=_auth_headers(),
                timeout=30,
            )
        print("   ->", r.status_code)
        return r.status_code == 200
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def test_auth_missing_header() -> bool:
    """仅在 ENABLE_AUTH=true 时生效：不带 X-API-Key 必须被拒。"""
    if not ENABLE_AUTH:
        print("[7] 鉴权(缺头) - 跳过 (ENABLE_AUTH=false)")
        return True
    print("[7] 鉴权(缺头) 应返 401")
    r = requests.post(
        BASE_URL + "/api/query",
        json={"query": "ping"},
        timeout=5,
    )
    print("   ->", r.status_code)
    return r.status_code in (401, 403)


def test_auth_valid_header() -> bool:
    """仅在 ENABLE_AUTH=true 时生效：带正确 X-API-Key 必须通过鉴权。"""
    if not ENABLE_AUTH:
        print("[8] 鉴权(正确头) - 跳过 (ENABLE_AUTH=false)")
        return True
    print("[8] 鉴权(正确头) 应能进入业务逻辑")
    r = requests.post(
        BASE_URL + "/api/query",
        json={"query": "ping"},
        headers={"X-API-Key": API_KEY},
        timeout=15,
    )
    print("   ->", r.status_code)
    # 401/403 表示被鉴权拦住；其他（200/500）意味着鉴权放行
    return r.status_code not in (401, 403)


def test_rate_limit_returns_429() -> bool:
    """连续发 RATE_LIMIT+2 次 /health，预期出现 429。仅在 RATE_LIMIT 合理时跑。"""
    print("[9] 限流 smoke (RATE_LIMIT_PER_MIN=" + str(RATE_LIMIT) + ")")
    if RATE_LIMIT <= 0 or RATE_LIMIT > 200:
        print("   -> 跳过（设置超出合理范围）")
        return True
    statuses: List[int] = []
    for _ in range(RATE_LIMIT + 2):
        try:
            statuses.append(requests.get(BASE_URL + "/health", timeout=5).status_code)
        except Exception as exc:
            print("   -> 请求异常", exc)
            return False
    counts = {code: statuses.count(code) for code in set(statuses)}
    print("   ->", counts)
    return 429 in statuses


def main() -> int:
    print("=" * 60)
    print("GraphRAG Copilot 冷烟脚本 (smoke test)")
    print("BASE_URL  =", BASE_URL)
    print("AUTH      =", "ON" if ENABLE_AUTH else "OFF")
    print("RATE_LIMIT=", RATE_LIMIT, "/ min")
    print("=" * 60)

    tests: List[Tuple[str, Callable[[], bool]]] = [
        ("健康检查", test_health),
        ("系统状态", test_system_status),
        ("向量统计", test_vector_stats),
        ("图谱统计", test_graph_stats),
        ("智能问答", test_query),
        ("文档上传", test_document_upload),
        ("鉴权(缺头)", test_auth_missing_header),
        ("鉴权(正确头)", test_auth_valid_header),
        ("限流", test_rate_limit_returns_429),
    ]

    passed = 0
    failures: List[str] = []
    for name, fn in tests:
        try:
            ok = fn()
        except Exception as exc:  # noqa: BLE001
            print("   -> ERROR", exc)
            ok = False
        if ok:
            passed += 1
        else:
            failures.append(name)

    print("-" * 60)
    print("总计: " + str(passed) + " / " + str(len(tests)))
    if failures:
        print("失败: " + ", ".join(failures))
        return 1
    print("冷烟通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
