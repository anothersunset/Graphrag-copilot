"""OpenAICompatLLMClient over a mock HTTP transport (no network)."""

from __future__ import annotations

import json

import httpx
import pytest
from graphrag_api.llm import OpenAICompatLLMClient


def _client(handler, *, model="deepseek-chat") -> OpenAICompatLLMClient:
    return OpenAICompatLLMClient(
        base_url="http://llm.test/v1",
        api_key="sk-test",
        model=model,
        transport=httpx.MockTransport(handler),
    )


def _chat_response(content: str) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"role": "assistant", "content": content}}]}
    )


def test_complete_returns_content_and_uses_configured_model_when_empty():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["model"] = json.loads(request.content)["model"]
        return _chat_response("答案 [chunk:1]")

    client = _client(handler)
    assert client.complete(model="", system="s", user="u") == "答案 [chunk:1]"
    assert seen["model"] == "deepseek-chat"


def test_complete_prefers_explicit_model():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["model"] = json.loads(request.content)["model"]
        return _chat_response("ok")

    _client(handler).complete(model="glm-4", system="s", user="u")
    assert seen["model"] == "glm-4"


def test_complete_sends_auth_and_endpoint():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        return _chat_response("ok")

    _client(handler).complete(model="", system="s", user="u")
    assert seen["url"] == "http://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"


def test_http_error_raises_runtime_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    client = _client(handler)
    with pytest.raises(RuntimeError, match="429"):
        client.complete(model="", system="s", user="u")


def test_malformed_body_raises_runtime_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    with pytest.raises(RuntimeError, match="response shape"):
        _client(handler).complete(model="", system="s", user="u")


def test_response_schema_parses_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response('{"intent": "factual", "_note": "done"}')

    result = _client(handler).complete(
        model="", system="s", user="u", response_schema=dict
    )
    assert result == {"intent": "factual", "_note": "done"}


def test_response_schema_unparsable_falls_back_to_raw():
    def handler(request: httpx.Request) -> httpx.Response:
        return _chat_response("抱歉，我做不到")

    result = _client(handler).complete(model="", system="s", user="u", response_schema=dict)
    assert result == {"raw_response": "抱歉，我做不到"}


def test_network_failure_wrapped():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(RuntimeError, match="LLM request failed"):
        _client(handler).complete(model="", system="s", user="u")
