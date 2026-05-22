"""Contextual Retrieval (Anthropic 2024) chunk preparation helper.

For every chunk, we ask an LLM to produce a 50-100 token natural-language
context describing where the chunk sits in the parent document. That
context is prepended to the chunk content *before* embedding/BM25
indexing. Reported recall lift in the original paper: ~49% reduction in
retrieval failures.

The LLM client is dependency-injected (anything exposing ``chat()``).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """<document>
{document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk}
</chunk>

Please give a short, natural-language context (50-100 tokens, single
paragraph, no bullet points, no markdown) that situates this chunk inside
the overall document so it can be retrieved on its own. Answer in the
same language as the chunk. Output only the context.
"""


@dataclass
class ContextualizedChunk:
    chunk_id: str
    original_content: str
    context: str
    augmented_content: str  # context + "\n\n" + original
    metadata: dict[str, Any]


class ContextualRetrievalGenerator:
    """Generate per-chunk situating context.

    Caller is responsible for batching calls at the document level so the
    LLM sees the full parent document once per chunk; use ``arun_batch``
    which fans out concurrently per chunk.
    """

    def __init__(
        self,
        *,
        llm: Any,
        concurrency: int = 8,
        max_context_tokens: int = 120,
    ) -> None:
        self.llm = llm
        self.concurrency = concurrency
        self.max_context_tokens = max_context_tokens
        self._sem = asyncio.Semaphore(concurrency)

    async def _generate_one(
        self, *, document: str, chunk_id: str, chunk: str, metadata: dict
    ) -> ContextualizedChunk:
        prompt = PROMPT_TEMPLATE.format(document=document, chunk=chunk)
        async with self._sem:
            try:
                response = await self.llm.achat(prompt)
                context = str(response).strip()
            except Exception:
                logger.exception("contextual gen failed for chunk_id=%s", chunk_id)
                context = ""
        augmented = f"{context}\n\n{chunk}" if context else chunk
        return ContextualizedChunk(
            chunk_id=chunk_id,
            original_content=chunk,
            context=context,
            augmented_content=augmented,
            metadata=dict(metadata),
        )

    async def arun_batch(
        self,
        *,
        document: str,
        chunks: Sequence[dict],
    ) -> list[ContextualizedChunk]:
        """Generate contexts for all chunks of a single document concurrently."""
        tasks = [
            self._generate_one(
                document=document,
                chunk_id=c["chunk_id"],
                chunk=c["content"],
                metadata=c.get("metadata", {}),
            )
            for c in chunks
        ]
        return await asyncio.gather(*tasks)
