"""Tests for app.core.security.require_api_key."""
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
