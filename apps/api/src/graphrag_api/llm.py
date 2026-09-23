"""OpenAI-compatible chat-completions client for the graph orchestrator.

Satisfies the ``graphrag_graph.contracts.LLMClient`` protocol with nothing
but ``httpx``, so DeepSeek / Zhipu / vLLM / OpenAI all work by pointing
``GRAPHRAG_LLM_BASE_URL`` at their endpoints. Kept sync on purpose: graph
nodes already offload blocking calls via ``asyncio.to_thread``.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from graphrag_graph.json_compat import extract_json_object

logger = logging.getLogger(__name__)

_JSON_INSTRUCTION = (
    "\n\n只输出一个 JSON 对象，不要输出任何其他文字或代码块围栏。"
)


class OpenAICompatLLMClient:
    """Minimal chat-completions client (no SDK dependency).

    ``complete(model=...)`` wins over the configured default when non-empty;
    the planner calls with ``model=""`` so the configured default is what
    actually serves planner and skeleton calls.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._default_timeout_s = timeout_s
        # httpx.Client is thread-safe for requests; graph nodes invoke
        # complete() via asyncio.to_thread, so a shared client also gets
        # connection pooling for free.
        self._client = httpx.Client(transport=transport)

    def _endpoint(self) -> str:
        if self._base_url.endswith("/chat/completions"):
            return self._base_url
        return f"{self._base_url}/chat/completions"

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        response_schema: type | None = None,
        timeout_s: float = 30.0,
    ) -> Any:
        use_model = model or self._model
        user_content = user
        if response_schema is not None:
            user_content = f"{user}{_JSON_INSTRUCTION}"
        payload = {
            "model": use_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        timeout = httpx.Timeout(timeout_s or self._default_timeout_s)
        try:
            response = self._client.post(
                self._endpoint(),
                json=payload,
                headers=headers,
                timeout=timeout,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        if response.status_code != 200:
            raise RuntimeError(
                f"LLM endpoint returned {response.status_code}: {response.text[:200]}"
            )
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(
                f"unexpected LLM response shape: {response.text[:300]}"
            ) from exc
        if response_schema is not None:
            # extract_json_object never fails: unparsable output comes back
            # as {"raw_response": ...}, the planner's established contract.
            return extract_json_object(content)
        return content
