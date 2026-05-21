"""Pluggable web-search route.

Disabled by default (returns empty list) so unit tests + CI never hit the
open web. Enable by passing an adapter or setting TAVILY_API_KEY.
"""
from __future__ import annotations

import logging
import os
from typing import Protocol

import httpx

from .base import RetrievalHit

logger = logging.getLogger(__name__)


class WebSearchAdapter(Protocol):
    async def asearch(self, query: str, *, top_k: int) -> list[RetrievalHit]: ...


class WebRetriever:
    """Web retriever facade.

    Tries adapters in order: explicitly-injected adapter > TAVILY_API_KEY
    Tavily adapter > no-op. Failures degrade silently to empty results;
    the orchestrator graph treats web as best-effort.
    """

    name = "web"

    def __init__(self, adapter: WebSearchAdapter | None = None, *, enabled: bool = True) -> None:
        self.enabled = enabled
        self._adapter = adapter or self._default_adapter()

    @staticmethod
    def _default_adapter() -> WebSearchAdapter | None:
        api_key = os.environ.get("TAVILY_API_KEY")
        if api_key:
            return TavilyAdapter(api_key=api_key)
        return None

    async def aretrieve(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        if not self.enabled or self._adapter is None:
            return []
        try:
            return await self._adapter.asearch(query, top_k=top_k)
        except Exception:
            logger.exception("web retrieval failed for query=%r", query)
            return []


class TavilyAdapter:
    """Thin Tavily search adapter — maps results to RetrievalHit."""

    BASE_URL = "https://api.tavily.com/search"

    def __init__(self, *, api_key: str, timeout_s: float = 8.0) -> None:
        self.api_key = api_key
        self.timeout_s = timeout_s

    async def asearch(self, query: str, *, top_k: int) -> list[RetrievalHit]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": top_k,
            "search_depth": "basic",
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.post(self.BASE_URL, json=payload)
            r.raise_for_status()
            data = r.json()
        hits: list[RetrievalHit] = []
        for i, item in enumerate(data.get("results", [])[:top_k]):
            hits.append(
                {
                    "chunk_id": f"web:{item.get('url', '')}",
                    "source": "web",
                    "score": float(item.get("score", 1.0 / (i + 1))),
                    "content": item.get("content", "")[:2000],
                    "metadata": {
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "published_date": item.get("published_date"),
                    },
                }
            )
        return hits
