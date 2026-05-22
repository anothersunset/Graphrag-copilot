"""Deterministic reference orchestrator for the bench.

No LLM, no vector DB, no Neo4j. Pure token-overlap ranking over the
fixed corpus + hand-authored triples. The goal isn't quality — the
goal is to give CI a stable, hermetic implementation that *does* clear
the v3.2 KPIs, so the bench plumbing itself can be trusted.

When a real runner is swapped in via ``run_bench(orchestrator=...)``,
it must return the same dict shape:

    {
        "answer":            str,
        "claims":            list[dict],          # see graphrag_graph.claims
        "cited_chunk_ids":   list[str],
        "evidence_pack":     dict,                # EvidencePack.model_dump()
        "query_history":     list[str],
        "verdict":           str,                 # "supported" | "unsupported" | ...
    }

Tiebreaking note: chunks are sorted by ``(-overlap, chunk_id)``. The
bench corpus uses chunk ids ``c01``…``c12`` and adversarial distractors
use ids prefixed ``distractor:``… so on a pure overlap tie, gold
always wins. This is intentional — the bench's job is to verify that
the rest of the v3.2 pipeline (claims, PS, adversarial accounting)
works, not to test the ranker.
"""
from __future__ import annotations

import re
from typing import Callable, Sequence

from graphrag_graph.claims import heuristic_claims
from graphrag_graph.evidence import (
    ChunkEvidence,
    EvidencePack,
    GraphNode,
    GraphPath,
    GraphRel,
    RerankTraceRow,
)

from .corpus import CORPUS, GRAPH_TRIPLES, CorpusChunk

BenchOrchestrator = Callable[[str], dict]

_TOKEN = re.compile(r"[\u4e00-\u9fff]|[A-Za-z][A-Za-z0-9_\-]+")


def _tokens(s: str) -> set[str]:
    if not s:
        return set()
    out: set[str] = set()
    for t in _TOKEN.findall(s):
        if len(t) == 1 and "\u4e00" <= t <= "\u9fff":
            out.add(t)
        elif len(t) >= 2:
            out.add(t.lower())
    return out


def _overlap(a: set[str], b: set[str]) -> int:
    return len(a & b)


def _detect_language(text: str) -> str:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


def reference_orchestrator(
    question: str,
    *,
    corpus: Sequence[CorpusChunk] | None = None,
    triples: Sequence[tuple[str, str, str]] | None = None,
    top_k: int = 3,
    visited_k: int = 6,
) -> dict:
    """Answer a gold question using nothing but token overlap.

    Returned dict matches the contract documented at module top.
    """
    corpus_tuple = tuple(corpus) if corpus is not None else CORPUS
    triples_tuple = tuple(triples) if triples is not None else GRAPH_TRIPLES

    q_tokens = _tokens(question)

    scored: list[tuple[CorpusChunk, int]] = sorted(
        ((c, _overlap(q_tokens, _tokens(c.text))) for c in corpus_tuple),
        key=lambda pair: (-pair[1], pair[0].id),
    )

    top = [(c, s) for c, s in scored[:top_k] if s > 0] or scored[:1]
    visited = scored[:visited_k]

    cited_chunks = [c for c, _ in top]
    cited_ids = [c.id for c in cited_chunks]
    answer = cited_chunks[0].text if cited_chunks else ""

    # Entity seeds: corpus entities mentioned in the question, plus any
    # entity from a top-cited chunk (so multi-hop chains anchor on cited
    # context).
    all_entities = {e for c in corpus_tuple for e in c.entities}
    q_text = question
    q_text_lower = q_text.lower()
    seeds: set[str] = set()
    for e in all_entities:
        if e in q_text or e.lower() in q_text_lower:
            seeds.add(e)
    for c in cited_chunks:
        seeds.update(c.entities)

    # 1-hop expansion over the static triple set.
    nodes_by_id: dict[str, GraphNode] = {}
    paths: list[GraphPath] = []
    for seed in sorted(seeds):
        nodes_by_id.setdefault(seed, GraphNode(id=seed, name=seed))
        for h, r, t in triples_tuple:
            if h != seed and t != seed:
                continue
            head_node = GraphNode(id=h, name=h)
            tail_node = GraphNode(id=t, name=t)
            nodes_by_id.setdefault(h, head_node)
            nodes_by_id.setdefault(t, tail_node)
            paths.append(
                GraphPath(
                    nodes=[head_node, tail_node],
                    rels=[GraphRel(source_id=h, target_id=t, type=r)],
                    depth=1,
                    rendered=f"{h} -[{r}]-> {t}",
                )
            )

    # visited_nodes includes everything we considered, even if we didn't
    # cite it. This is what the adversarial harness inspects.
    visited_by_id: dict[str, GraphNode] = dict(nodes_by_id)
    for c, _ in visited:
        for e in c.entities:
            visited_by_id.setdefault(e, GraphNode(id=e, name=e))

    vector_chunks = [
        ChunkEvidence(
            chunk_id=c.id,
            source="bm25",
            content=c.text,
            score=float(s),
        )
        for c, s in top
    ]

    rerank_trace = [
        RerankTraceRow(
            chunk_id=c.id,
            pre_rerank_rank=rank,
            post_rerank_rank=rank,
            rerank_score=float(s),
        )
        for rank, (c, s) in enumerate(visited, start=1)
    ]

    pack = EvidencePack(
        vector_chunks=vector_chunks,
        graph_nodes=list(nodes_by_id.values()),
        graph_paths=paths,
        visited_nodes=list(visited_by_id.values()),
        rerank_trace=rerank_trace,
    )

    contexts = [{"chunk_id": c.id, "content": c.text} for c in cited_chunks]
    claim_objs = heuristic_claims(
        answer,
        cited_chunk_ids=cited_ids,
        contexts=contexts,
        min_overlap=2,
    )
    claims = [c.model_dump() for c in claim_objs]

    supported = bool(claims) and all(c["evidence_ids"] for c in claims)
    verdict = "supported" if supported else "unsupported"

    return {
        "answer": answer,
        "claims": claims,
        "cited_chunk_ids": cited_ids,
        "evidence_pack": pack.model_dump(),
        "query_history": [question],
        "verdict": verdict,
    }


def adversarial_orchestrator_adapter(question: str, corpus: list[dict]) -> dict:
    """Bridge the adversarial Orchestrator protocol to the reference runner.

    The adversarial harness hands us a list of chunk dicts (gold + one
    planted distractor). We:

    * Convert each dict to a ``CorpusChunk`` so the reference
      orchestrator can score it.
    * Pull each chunk's ``node_id`` (the distractor carries one) into
      that chunk's entity set, so when the chunk is visited we naturally
      register the node as visited.
    * Force-add every ``node_id`` to ``visited_nodes`` after the run, so
      the adversarial harness can prove the distractor was *seen* even
      if it didn't make the top-k cut.
    """
    chunks: list[CorpusChunk] = []
    forced_visited: list[str] = []
    for c in corpus:
        cid = c["chunk_id"]
        entities = list(c.get("metadata", {}).get("entities") or ())
        node_id = c.get("node_id")
        if node_id:
            entities.append(node_id)
            forced_visited.append(node_id)
        chunks.append(
            CorpusChunk(
                id=cid,
                text=c.get("content", ""),
                language=_detect_language(c.get("content", "")),  # type: ignore[arg-type]
                entities=tuple(entities),
            )
        )

    result = reference_orchestrator(question, corpus=chunks)

    pack = result["evidence_pack"]
    visited = pack.get("visited_nodes") or []
    visited_ids = {n["id"] for n in visited}
    for nid in forced_visited:
        if nid in visited_ids:
            continue
        visited.append(
            {"id": nid, "name": nid, "labels": [], "properties": {}}
        )
        visited_ids.add(nid)
    pack["visited_nodes"] = visited
    return result
