"""Contextual Retrieval generator — fake LLM round-trip."""

from __future__ import annotations

import asyncio

from graphrag_retrieval.contextual import ContextualRetrievalGenerator


class FakeLLM:
    def __init__(self, prefix: str = "CTX:"):
        self.prefix = prefix
        self.calls: list[str] = []

    async def achat(self, prompt: str) -> str:
        self.calls.append(prompt)
        return f"{self.prefix} short context placeholder."


def test_generator_prepends_context_and_preserves_metadata():
    llm = FakeLLM()
    gen = ContextualRetrievalGenerator(llm=llm)
    out = asyncio.run(
        gen.arun_batch(
            document="Full doc body about GraphRAG.",
            chunks=[
                {"chunk_id": "c1", "content": "GraphRAG uses Neo4j.", "metadata": {"page": 1}},
                {"chunk_id": "c2", "content": "BM25 is sparse.", "metadata": {"page": 2}},
            ],
        )
    )
    assert len(out) == 2
    assert out[0].chunk_id == "c1"
    assert out[0].context.startswith("CTX:")
    assert out[0].original_content == "GraphRAG uses Neo4j."
    assert out[0].original_content in out[0].augmented_content
    assert out[0].context in out[0].augmented_content
    assert out[0].metadata == {"page": 1}
    # llm was called twice, once per chunk
    assert len(llm.calls) == 2


def test_generator_handles_llm_failure_gracefully():
    class FailingLLM:
        async def achat(self, prompt: str) -> str:
            raise RuntimeError("boom")

    gen = ContextualRetrievalGenerator(llm=FailingLLM())
    out = asyncio.run(
        gen.arun_batch(
            document="doc",
            chunks=[{"chunk_id": "c1", "content": "chunk body", "metadata": {}}],
        )
    )
    # On LLM failure, context is empty but original content is preserved
    assert out[0].context == ""
    assert out[0].augmented_content == "chunk body"
