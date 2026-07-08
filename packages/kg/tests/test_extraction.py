"""LLM extraction (gleaning + JSON robustness) and co-occurrence fallback."""

from __future__ import annotations

from graphrag_kg.extraction import (
    CooccurrenceExtractor,
    LLMEntityExtractor,
    extract_balanced_json,
)


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    def __call__(self, system: str, user: str) -> str:
        self.calls.append(user)
        if self.responses:
            return self.responses.pop(0)
        return '{"entities": [], "relations": []}'


# ---------------------------------------------------------------- JSON --


def test_balanced_json_ignores_thinking_tokens_and_second_object():
    raw = (
        "Let me think about the entities step by step...\n"
        '{"entities": [{"name": "Neo4j", "type": "Technology"}], "relations": []}\n'
        'And also {"entities": [{"name": "WRONG"}], "relations": []}'
    )
    parsed = extract_balanced_json(raw)
    assert parsed["entities"][0]["name"] == "Neo4j"


def test_balanced_json_handles_braces_inside_strings():
    raw = '{"entities": [{"name": "curly {brace} corp", "type": "Organization"}], "relations": []}'
    parsed = extract_balanced_json(raw)
    assert parsed["entities"][0]["name"] == "curly {brace} corp"


def test_balanced_json_returns_empty_on_garbage():
    assert extract_balanced_json("no json here") == {}
    assert extract_balanced_json("{broken json") == {}


# ------------------------------------------------------------- gleaning --


def test_gleaning_recovers_missed_entities_and_dedups():
    llm = FakeLLM(
        [
            '{"entities": [{"name": "GraphRAG", "type": "Technology"},'
            ' {"name": "Neo4j", "type": "Technology"}],'
            ' "relations": [{"source": "GraphRAG", "target": "Neo4j", "type": "USES"}]}',
            # gleaning pass 1: one genuinely new entity + one duplicate
            '{"entities": [{"name": "Cypher", "type": "Technology"},'
            ' {"name": "graphrag", "type": "Technology"}],'
            ' "relations": [{"source": "Neo4j", "target": "Cypher", "type": "USES"}]}',
            # gleaning pass 2: nothing left
            '{"entities": [], "relations": []}',
        ]
    )
    extractor = LLMEntityExtractor(llm=llm, max_gleanings=3)
    result = extractor.extract("c1", "GraphRAG uses Neo4j which is queried via Cypher.")

    names = sorted(e.name for e in result.entities)
    assert names == ["Cypher", "GraphRAG", "Neo4j"]  # dup "graphrag" dropped
    assert len(result.relations) == 2
    # first pass + gleaning-1 + gleaning-2 (early stop before pass 3)
    assert len(llm.calls) == 3
    assert all(e.source_chunk_ids == ["c1"] for e in result.entities)


def test_max_gleanings_zero_runs_single_pass():
    llm = FakeLLM(['{"entities": [{"name": "A"}], "relations": []}'])
    result = LLMEntityExtractor(llm=llm, max_gleanings=0).extract("c1", "text about A")
    assert len(llm.calls) == 1
    assert result.entities[0].name == "A"


def test_llm_failure_degrades_to_empty_result():
    def broken(system: str, user: str) -> str:
        raise RuntimeError("api down")

    result = LLMEntityExtractor(llm=broken).extract("c1", "some text")
    assert result.entities == [] and result.relations == []


def test_unknown_types_are_coerced_to_defaults():
    llm = FakeLLM(
        [
            '{"entities": [{"name": "X", "type": "Alien"}],'
            ' "relations": [{"source": "X", "target": "Y", "type": "TELEPORTS"}]}'
        ]
    )
    result = LLMEntityExtractor(llm=llm, max_gleanings=0).extract("c1", "text")
    assert result.entities[0].type == "Concept"
    assert result.relations[0].type == "RELATED_TO"


# -------------------------------------------------------- co-occurrence --


def test_cooccurrence_extractor_is_deterministic_and_offline():
    text = "GraphRAG uses Neo4j for storage. Neo4j is queried via Cypher. BM25 handles keywords."
    ex = CooccurrenceExtractor()
    r1 = ex.extract("c1", text)
    r2 = ex.extract("c1", text)
    names = {e.name for e in r1.entities}
    assert {"GraphRAG", "Neo4j", "Cypher", "BM25"} <= names
    assert [e.name for e in r1.entities] == [e.name for e in r2.entities]
    # sentence co-occurrence produces a GraphRAG—Neo4j relation
    pairs = {(r.source, r.target) for r in r1.relations}
    assert ("GraphRAG", "Neo4j") in pairs or ("Neo4j", "GraphRAG") in pairs
    # but no cross-sentence relation between GraphRAG and BM25
    assert ("BM25", "GraphRAG") not in pairs and ("GraphRAG", "BM25") not in pairs


def test_cooccurrence_empty_text():
    result = CooccurrenceExtractor().extract("c1", "   ")
    assert result.entities == [] and result.relations == []
