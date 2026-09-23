"""Gold semantic-ID -> chunk-ID map integrity tests (backlog P0-2c).

The map is hand-annotated; these tests keep it honest:
- every gold id used by every benchmark dataset must have a mapping
- every mapped chunk id must exist in the persisted v1 corpus
- expansion must be deterministic and keep unmapped ids visible
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.datasets import expand_gold_context_ids, load_benchmark, load_gold_context_map

REPO = Path(__file__).resolve().parents[2]
DATASETS = [
    REPO / "eval/datasets/seed_benchmark.jsonl",
    REPO / "eval/datasets/benchmark_20.jsonl",
    REPO / "eval/datasets/benchmark_50.jsonl",
]
CORPUS = REPO / "backend/data/vector_db/bm25_documents.json"


def _dataset_gold_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ids.update(json.loads(line).get("gold_context_ids", []))
    return ids


def _corpus_chunk_ids() -> set[str]:
    docs = json.load(open(CORPUS, encoding="utf-8"))
    return {f"{d['metadata']['file_name']}#{d['metadata']['chunk_index']}" for d in docs}


def test_gold_map_loads_and_has_expected_size():
    mapping = load_gold_context_map()
    assert len(mapping) >= 34
    assert all(isinstance(v, list) and v for v in mapping.values())


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda p: p.name)
def test_every_dataset_gold_id_is_mapped(dataset):
    if not dataset.exists():
        pytest.skip(f"{dataset.name} not present")
    mapping = load_gold_context_map()
    unmapped = _dataset_gold_ids(dataset) - set(mapping)
    assert not unmapped, f"gold ids without chunk mapping: {sorted(unmapped)}"


def test_mapped_chunk_ids_exist_in_corpus():
    if not CORPUS.exists():
        pytest.skip("persisted v1 corpus not present")
    corpus = _corpus_chunk_ids()
    mapping = load_gold_context_map()
    unknown = {c for chunks in mapping.values() for c in chunks} - corpus
    assert not unknown, f"mapped chunk ids missing from corpus: {sorted(unknown)}"


def test_expansion_is_deterministic_and_complete():
    mapping = load_gold_context_map()
    gold = sorted(mapping)[:5]
    once = expand_gold_context_ids(gold)
    twice = expand_gold_context_ids(gold)
    assert once == twice
    expected = [c for g in gold for c in mapping[g]]
    assert once == expected


def test_unmapped_ids_pass_through_visibly():
    assert expand_gold_context_ids(["not-a-real-id"]) == ["not-a-real-id"]


def test_load_benchmark_still_works_with_map_present():
    seed = REPO / "eval/datasets/seed_benchmark.jsonl"
    cases = load_benchmark(str(seed))
    assert cases, "seed benchmark must still load"
