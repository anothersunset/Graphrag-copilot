# graphrag-retrieval

Four-route retrieval for GraphRAG Copilot v3.1.

## Routes

| route   | engine                                | sparse / dense | landed |
| ------- | ------------------------------------- | -------------- | ------ |
| vector  | Qdrant + bge-large-zh-v1.5 (512-dim)  | dense          | W3     |
| bm25    | rank_bm25 + jieba tokenizer           | sparse         | W3     |
| kg      | Neo4j 5.x via Cypher subgraph query   | structured     | W3     |
| web     | Tavily / Brave Search (optional)      | external       | W3     |

## Fusion

Reciprocal Rank Fusion (RRF) on the union of route outputs, then optional
BGE-Reranker-v2-m3 cross-encoder rerank to a final top-K.

## Quick start

```python
import asyncio
from graphrag_retrieval import (
    VectorRetriever, BM25Retriever, KGRetriever, WebRetriever,
    BGEReranker, rrf_fuse,
)

async def main():
    vec = VectorRetriever(url="http://localhost:6333", collection="docs")
    bm25 = BM25Retriever.load("data/bm25.pkl")
    kg = KGRetriever(uri="bolt://localhost:7687", auth=("neo4j", "..."))
    web = WebRetriever()  # disabled by default

    routes = await asyncio.gather(
        vec.aretrieve("What is GraphRAG?", top_k=20),
        bm25.aretrieve("What is GraphRAG?", top_k=20),
        kg.aretrieve("What is GraphRAG?", top_k=20),
    )
    fused = rrf_fuse(routes, k=60)
    reranker = BGEReranker()
    top5 = reranker.rerank("What is GraphRAG?", fused, top_k=5)
```

## Status

W3 (2026-06-04 → 2026-06-10) — base + vector + bm25 land first, then
kg + web + reranker + Contextual Retrieval chunking helper.
