import json
import requests
import time

BASE_URL = "http://localhost:8000"

def score_answer(answer, expected_keywords):
    if not expected_keywords:
        return 0.0
    hit = 0
    for keyword in expected_keywords:
        if keyword.lower() in answer.lower():
            hit += 1
    return hit / len(expected_keywords)

def main():
    with open("eval/questions.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    results = []

    for item in questions:
        start = time.time()
        response = requests.post(
            BASE_URL + "/api/query",
            json={"query": item["question"], "top_k": 5},
            timeout=120,
        )
        latency = time.time() - start

        if response.status_code != 200:
            results.append({
                "id": item["id"],
                "question": item["question"],
                "score": 0.0,
                "latency": latency,
                "error": response.text,
            })
            continue

        data = response.json()
        answer = data.get("answer", "")
        score = score_answer(answer, item["expected_keywords"])

        results.append({
            "id": item["id"],
            "type": item["type"],
            "question": item["question"],
            "score": score,
            "confidence": data.get("confidence", 0.0),
            "sources_count": len(data.get("sources", [])),
            "latency": latency,
        })

    avg_score = sum(r["score"] for r in results) / max(len(results), 1)

    print("Evaluation Results")
    print("=" * 50)
    for r in results:
        print(r["id"], "|", r.get("type", "unknown"), "|",
              "score=" + format(r["score"], ".2f"), "|",
              "sources=" + str(r.get("sources_count", 0)), "|",
              "latency=" + format(r.get("latency", 0), ".2f") + "s")
    print("-" * 50)
    print("Average score:", format(avg_score, ".2f"))

if __name__ == "__main__":
    main()
