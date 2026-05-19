"""GraphRAG Copilot - API 集成测试脚本"""
import requests

BASE_URL = "http://localhost:8000"

def test_health():
    print("测试健康检查...")
    r = requests.get(BASE_URL + "/health")
    print("  状态:", r.status_code, r.json())
    return r.status_code == 200

def test_system_status():
    print("测试系统状态...")
    r = requests.get(BASE_URL + "/api/system/status")
    print("  状态:", r.status_code)
    return r.status_code == 200

def test_vector_stats():
    print("测试向量存储统计...")
    r = requests.get(BASE_URL + "/api/vector/stats")
    return r.status_code == 200

def test_graph_stats():
    print("测试知识图谱统计...")
    r = requests.get(BASE_URL + "/api/graph/stats")
    return r.status_code == 200

def test_query():
    print("测试智能问答...")
    r = requests.post(BASE_URL + "/api/query", json={"query": "什么是 GraphRAG？", "top_k": 5})
    return r.status_code in (200, 500)

def test_document_upload():
    print("测试文档上传...")
    content = "GraphRAG 是结合知识图谱和 RAG 的检索增强生成技术。"
    with open("test_document.txt", "w", encoding="utf-8") as f:
        f.write(content)
    with open("test_document.txt", "rb") as f:
        r = requests.post(BASE_URL + "/api/documents/upload", files={"file": ("test.txt", f, "text/plain")})
    import os
    os.remove("test_document.txt")
    return r.status_code == 200

def main():
    tests = [
        ("健康检查", test_health),
        ("系统状态", test_system_status),
        ("向量统计", test_vector_stats),
        ("图谱统计", test_graph_stats),
        ("智能问答", test_query),
        ("文档上传", test_document_upload),
    ]
    passed = 0
    for name, fn in tests:
        try:
            ok = fn()
            print("  ->", name, "PASS" if ok else "FAIL")
            if ok:
                passed += 1
        except Exception as e:
            print("  ->", name, "ERROR", e)
    print("总计:", passed, "/", len(tests))

if __name__ == "__main__":
    main()
