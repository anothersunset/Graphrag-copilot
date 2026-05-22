"""Markdown splitter correctness."""
from __future__ import annotations

from graphrag_parsers.markdown import MarkdownSplitter


MD = """# Project

Intro paragraph about the project.

## Architecture

The system has three layers.

### Retrieval

We use four routes.

```python
def rrf_fuse(routes):
    # multi-line code fence — must stay atomic
    return sorted(routes, key=lambda r: r.score)
```

## Eval

We use RAGAS and DeepEval.
"""


def test_breadcrumbs_track_heading_stack():
    s = MarkdownSplitter(max_tokens=512, overlap_tokens=32)
    chunks = list(s.split(doc_id="md1", text=MD))
    crumbs = {c.metadata["breadcrumbs"] for c in chunks}
    # All three headings should appear in some breadcrumb path
    assert any("Project > Architecture > Retrieval" == c for c in crumbs)
    assert any("Project > Architecture" == c for c in crumbs)
    assert any("Project > Eval" == c for c in crumbs)


def test_code_fence_stays_atomic():
    s = MarkdownSplitter(max_tokens=512, overlap_tokens=32)
    chunks = list(s.split(doc_id="md2", text=MD))
    # The chunk containing the fence start must also contain the closing fence.
    found = False
    for ch in chunks:
        if "```python" in ch.content:
            assert ch.content.count("```") >= 2
            found = True
    assert found, "code fence not located in any chunk"


def test_empty_markdown_yields_no_chunks():
    s = MarkdownSplitter()
    assert list(s.split(doc_id="md3", text="")) == []
