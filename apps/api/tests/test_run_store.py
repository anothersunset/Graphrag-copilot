import pytest
from graphrag_api.run_store import RunStore, SqliteRunStore, build_run_store


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


def test_sqlite_store_same_contract(tmp_path) -> None:
    store = SqliteRunStore(tmp_path / "runs.db", capacity=2, ttl_seconds=60)
    store.put("a", {"value": [1]})
    store.put("b", {"value": [2]})
    returned = store.get("a")
    assert returned is not None
    returned["value"].append(9)
    assert store.get("a") == {"value": [1]}  # deep-copy semantics

    store.put("c", {"value": [3]})
    assert store.get("b") is None  # LRU eviction via last_read
    assert store.get("a") is not None


def test_sqlite_store_survives_reopen(tmp_path) -> None:
    db = tmp_path / "runs.db"
    first = SqliteRunStore(db, capacity=10, ttl_seconds=3600)
    first.put("run-1", {"answer": "yes"})
    first.close()

    second = SqliteRunStore(db, capacity=10, ttl_seconds=3600)
    assert second.get("run-1") == {"answer": "yes"}


def test_sqlite_store_ttl_expiry(tmp_path) -> None:
    store = SqliteRunStore(tmp_path / "runs.db", capacity=10, ttl_seconds=1)
    store.put("run-1", {"answer": "stale"})
    # backdate the row past the TTL
    store._conn.execute("UPDATE runs SET expires_at = expires_at - 5")
    store._conn.commit()
    assert store.get("run-1") is None


def test_build_run_store_resolves_backends(tmp_path) -> None:
    assert isinstance(build_run_store(None, capacity=5, ttl_seconds=60), RunStore)
    assert isinstance(build_run_store("memory://", capacity=5, ttl_seconds=60), RunStore)
    sqlite_store = build_run_store(
        f"sqlite:///{tmp_path / 'runs.db'}", capacity=5, ttl_seconds=60
    )
    assert isinstance(sqlite_store, SqliteRunStore)
    with pytest.raises(ValueError, match="unsupported"):
        build_run_store("redis://nowhere", capacity=5, ttl_seconds=60)
