"""SemanticChunker correctness."""

from __future__ import annotations

from graphrag_parsers.chunker import SemanticChunker


def test_short_text_emits_single_chunk():
    c = SemanticChunker(max_tokens=512, overlap_tokens=32)
    chunks = list(c.split(doc_id="d1", text="这是一句话。这是另一句。"))
    assert len(chunks) == 1
    assert chunks[0].doc_id == "d1"
    assert chunks[0].metadata["chunk_index"] == 0


def test_long_text_splits_into_multiple_chunks_with_budget():
    sentences = ["这是第" + str(i) + "句。" for i in range(200)]
    long_text = "".join(sentences)
    c = SemanticChunker(max_tokens=50, overlap_tokens=10)
    chunks = list(c.split(doc_id="d2", text=long_text))
    assert len(chunks) > 1
    for ch in chunks:
        assert ch.metadata["token_count"] <= 50 + 10  # budget + overlap slack


def test_overlap_preserves_tail_into_next_chunk():
    text = " ".join([f"sentence-{i}." for i in range(60)])
    c = SemanticChunker(max_tokens=20, overlap_tokens=8)
    chunks = list(c.split(doc_id="d3", text=text))
    assert len(chunks) >= 2
    # Tail of chunk[0] should appear at head of chunk[1] (overlap window)
    last_word_of_first = chunks[0].content.split()[-1]
    assert last_word_of_first in chunks[1].content


def test_chunk_id_is_stable_and_unique():
    text = "一句。二句。三句。四句。"
    c = SemanticChunker(max_tokens=4, overlap_tokens=1)
    a = list(c.split(doc_id="d4", text=text))
    b = list(c.split(doc_id="d4", text=text))
    assert [x.chunk_id for x in a] == [x.chunk_id for x in b]
    assert len({x.chunk_id for x in a}) == len(a)


def test_overlap_must_be_smaller_than_budget():
    import pytest

    with pytest.raises(ValueError):
        SemanticChunker(max_tokens=10, overlap_tokens=20)
