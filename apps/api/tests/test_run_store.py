from graphrag_api.run_store import RunStore


def test_run_store_evicts_oldest_and_returns_copies() -> None:
    store = RunStore(capacity=2, ttl_seconds=60)
    store.put("a", {"value": [1]})
    store.put("b", {"value": [2]})
    returned = store.get("a")
    assert returned is not None
    returned["value"].append(9)
    assert store.get("a") == {"value": [1]}

    store.put("c", {"value": [3]})
    assert store.get("b") is None
    assert store.get("a") is not None
