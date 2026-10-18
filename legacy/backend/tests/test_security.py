"""Tests for app.core.security.require_api_key and slowapi rate limiting."""
import pytest
from fastapi import HTTPException

from app.core import security
from config.settings import settings


@pytest.mark.asyncio
async def test_auth_disabled_returns_marker(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AUTH", False)
    monkeypatch.setattr(settings, "API_KEYS", "")
    assert await security.require_api_key(x_api_key=None) == "auth_disabled"


@pytest.mark.asyncio
async def test_auth_enabled_missing_header_raises_401(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AUTH", True)
    monkeypatch.setattr(settings, "API_KEYS", "test-key-1,test-key-2")
    with pytest.raises(HTTPException) as exc:
        await security.require_api_key(x_api_key=None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_enabled_valid_header_passes(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AUTH", True)
    monkeypatch.setattr(settings, "API_KEYS", "test-key-1,test-key-2")
    result = await security.require_api_key(x_api_key="test-key-2")
    assert result == "test-key-2"


@pytest.mark.asyncio
async def test_auth_enabled_but_no_keys_raises_503(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_AUTH", True)
    monkeypatch.setattr(settings, "API_KEYS", "")
    with pytest.raises(HTTPException) as exc:
        await security.require_api_key(x_api_key="anything")
    assert exc.value.status_code == 503


def test_rate_limit_returns_429_after_threshold():
    """验证 slowapi Limiter + SlowAPIMiddleware 超过默认限额后返回 429。

    使用内联极简 FastAPI 应用，避免拉起 vector/kg/llm 服务。这验证了 main.py
    中同样的限流接线方式（Limiter + default_limits + SlowAPIMiddleware）是可用的。
    """
    slowapi = pytest.importorskip("slowapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address, default_limits=["3/minute"])
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    client = TestClient(app)
    statuses = [client.get("/ping").status_code for _ in range(5)]

    # 前 3 次 200，后面应出现 429
    assert statuses.count(200) == 3, f"实际状态: {statuses}"
    assert 429 in statuses, f"未触发限流，状态: {statuses}"
    assert statuses[-1] == 429
