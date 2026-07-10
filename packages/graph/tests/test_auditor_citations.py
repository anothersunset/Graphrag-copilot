from graphrag_graph.nodes.auditor import auditor_node


def _state(**overrides):
    state = {
        "question": "What is GraphRAG?",
        "answer": "GraphRAG combines graph and retrieval.",
        "fused_hits": [
            {
                "chunk_id": "c1",
                "content": "GraphRAG uses a graph.",
                "source": "kg",
                "score": 0.9,
            }
        ],
        "citations": [],
    }
    state.update(overrides)
    return state


def test_auditor_fails_answer_without_explicit_citation():
    out = auditor_node(_state())
    assert out["auditor_verdict"] == "fail"
    assert out["cited_chunk_ids"] == []


def test_auditor_rejects_unknown_generated_citation():
    out = auditor_node(_state(citations=[{"chunk_id": "missing"}]))
    assert out["auditor_verdict"] == "fail"
    assert out["cited_chunk_ids"] == []


def test_auditor_accepts_valid_generated_citation():
    out = auditor_node(
        _state(
            answer="GraphRAG uses a graph [chunk:1].",
            citations=[{"chunk_id": "c1"}],
        )
    )
    assert out["cited_chunk_ids"] == ["c1"]
