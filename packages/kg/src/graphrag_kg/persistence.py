"""Persist a built ``GraphRAGIndex`` to disk and load it back.

Why: ``build_index`` with an LLM extractor (gleaning) plus abstractive
community summaries costs real money and minutes; rebuilding it from the
raw corpus on every API restart silently degrades the index back to
co-occurrence quality. The persistence layer — the same role
LlamaIndex's ``storage_context.persist`` plays — lets the ingest CLI
build once and the API boot straight from the artifact:

    uv run --package graphrag-api python -m graphrag_api.ingest \
        --save-index data/index/index.json
    GRAPHRAG_INDEX_PATH=data/index/index.json make api

Format (version 1): one JSON document with the networkx node-link
encoding of the entity graph (edge ``types`` sets stored as sorted
lists), the community reports, and the chunk texts. The alias map is
reconstructed on load instead of serialized — it is fully derivable
from node ids + node ``aliases`` attributes.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from .graph_store import KnowledgeGraphIndex
from .models import CommunityReport
from .pipeline import GraphRAGIndex
from .resolution import normalize_name

FORMAT_VERSION = 1


def save_index(index: GraphRAGIndex, path: str | Path) -> Path:
    """Serialize the index; returns the path written."""
    # GraphRAGIndex.graph is the KnowledgeGraphIndex wrapper; the networkx
    # graph it wraps is what node_link_data consumes. The edge-list key is
    # pinned to "links" so the on-disk format stays stable across networkx
    # versions (3.4 flipped the default to "edges").
    data = nx.node_link_data(index.graph.graph, edges="links")
    # Edge ``types`` is a set in memory — JSON needs a list. Everything
    # else (str node ids, list chunk_ids, floats) is already JSON-safe.
    for link in data["links"]:
        types = link.get("types", [])
        link["types"] = sorted(types) if isinstance(types, (set, frozenset)) else list(types)

    payload = {
        "version": FORMAT_VERSION,
        "graph": data,
        "communities": [report.model_dump() for report in index.communities],
        "chunk_texts": index.chunk_texts,
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return target


def load_index(path: str | Path) -> GraphRAGIndex:
    """Rebuild a ``GraphRAGIndex`` saved by :func:`save_index`."""
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    version = payload.get("version")
    if version != FORMAT_VERSION:
        raise ValueError(
            f"unsupported index format version {version!r} in {source} "
            f"(expected {FORMAT_VERSION}); rebuild the index with the ingest CLI"
        )

    graph = nx.node_link_graph(payload["graph"], edges="links")
    store = KnowledgeGraphIndex()
    store.graph = graph
    for _a, _b, data in graph.edges(data=True):
        data["types"] = set(data.get("types", []))

    # The alias map is derived state — node ids and their alias attributes
    # fully determine it (mirrors KnowledgeGraphIndex.add).
    for node, data in graph.nodes(data=True):
        store._alias_map[normalize_name(node)] = node
        for alias in data.get("aliases", []):
            store._alias_map[normalize_name(alias)] = node

    return GraphRAGIndex(
        graph=store,
        communities=[CommunityReport.model_validate(row) for row in payload["communities"]],
        chunk_texts=payload["chunk_texts"],
    )
