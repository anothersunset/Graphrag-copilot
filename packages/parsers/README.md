# graphrag-parsers

Document parsing + chunking utilities for GraphRAG Copilot v3.1.

## Capabilities

| feature              | source                                | landed |
| -------------------- | ------------------------------------- | ------ |
| Semantic chunker     | regex sentence split + token budget   | W4     |
| Markdown splitter    | header-aware with breadcrumbs         | W4     |
| Late Chunking        | Jina 2024 (full-doc encode + pool)    | W4     |

Chunks emitted by all paths share a single `ChunkRecord` shape so the
retrieval package can index them uniformly.

## Quick start

```python
from graphrag_parsers import SemanticChunker, MarkdownSplitter

chunker = SemanticChunker(max_tokens=512, overlap_tokens=64)
for chunk in chunker.split(doc_id="d1", text=long_text):
    print(chunk.chunk_id, len(chunk.content))

md = MarkdownSplitter()
for chunk in md.split(doc_id="d2", text=markdown_text):
    print(chunk.metadata["breadcrumbs"], chunk.content[:80])
```
