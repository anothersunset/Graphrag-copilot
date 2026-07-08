"""Hierarchical community detection + community summarization.

This is the index-side half of Microsoft GraphRAG global search
(Edge et al., 2024): partition the entity graph into communities,
summarize each community once at index time, then answer corpus-level
questions by retrieving over the summaries instead of raw chunks.

Detection uses the Louvain method as implemented in networkx
(``louvain_communities``) — same modularity-maximization family as the
Leiden algorithm the paper uses. Leiden additionally guarantees
well-connected communities; the detector interface (``levels``,
``seed``, weighted edges) is kept algorithm-agnostic so ``leidenalg``
can be swapped in where the igraph C dependency is acceptable.

Hierarchy: level 0 = whole-graph partition; any level-0 community
larger than ``max_community_size`` is re-partitioned into level-1
sub-communities, mirroring GraphRAG's multi-level report tree
(coarse level for broad questions, finer level for narrower ones).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import networkx as nx

from .graph_store import KnowledgeGraphIndex
from .models import CommunityReport

logger = logging.getLogger(__name__)

# (system, user) -> completion text
ChatFn = Callable[[str, str], str]

_SUMMARY_SYSTEM = (
    "你是知识图谱分析专家。给定一个实体社区（实体+描述+关系），"
    "输出一段 100-200 字的中文摘要，概括这个社区的主题、核心实体及它们的关系。"
    "第一行输出一个 5-10 字的标题，其后输出摘要正文，不要输出其他内容。"
)


# A partition function maps a (sub)graph to a list of node communities.
# Default = Louvain; inject leidenalg-backed partitioning (or a fake, in
# tests) without touching the hierarchy logic.
PartitionFn = Callable[[nx.Graph], list[set[str]]]


def detect_communities(
    index: KnowledgeGraphIndex,
    *,
    max_community_size: int = 20,
    min_community_size: int = 2,
    seed: int = 42,
    partition_fn: PartitionFn | None = None,
) -> list[CommunityReport]:
    """Two-level partition → CommunityReport skeletons (no summaries)."""
    g = index.graph
    if g.number_of_nodes() == 0:
        return []

    partition: PartitionFn = partition_fn or (
        lambda graph: nx.community.louvain_communities(graph, weight="weight", seed=seed)
    )

    total_degree = sum(d for _, d in g.degree(weight="weight")) or 1.0
    reports: list[CommunityReport] = []

    level0 = partition(g)
    for i, members in enumerate(sorted(level0, key=len, reverse=True)):
        members = set(members)
        if len(members) < min_community_size:
            continue
        reports.append(_skeleton(index, f"c0.{i}", 0, members, total_degree))

        if len(members) > max_community_size:
            sub = g.subgraph(members)
            level1 = partition(sub)
            for j, sub_members in enumerate(sorted(level1, key=len, reverse=True)):
                sub_members = set(sub_members)
                if min_community_size <= len(sub_members) < len(members):
                    reports.append(
                        _skeleton(index, f"c0.{i}/c1.{j}", 1, sub_members, total_degree)
                    )
    return reports


def _skeleton(
    index: KnowledgeGraphIndex,
    community_id: str,
    level: int,
    members: set[str],
    total_degree: float,
) -> CommunityReport:
    g = index.graph
    chunk_ids: dict[str, None] = {}
    for n in members:
        for c in index.chunk_ids_for(n):
            chunk_ids.setdefault(c, None)
    degree = sum(d for _, d in g.degree(members, weight="weight"))
    return CommunityReport(
        community_id=community_id,
        level=level,
        entity_ids=sorted(members),
        chunk_ids=list(chunk_ids),
        size=len(members),
        rank=round(degree / total_degree, 4),
    )


class CommunitySummarizer:
    """Fill titles + summaries on detected communities.

    With an injected LLM each community gets a real abstractive summary;
    without one, a deterministic template summary is produced from the
    highest-degree member entities and their strongest intra-community
    relations — lower quality, but keeps the global-search route alive
    offline (and gives tests a stable target).
    """

    def __init__(self, *, llm: ChatFn | None = None, max_members_in_prompt: int = 15) -> None:
        self._llm = llm
        self.max_members = max_members_in_prompt

    def summarize(
        self, index: KnowledgeGraphIndex, reports: list[CommunityReport]
    ) -> list[CommunityReport]:
        for report in reports:
            context = self._community_context(index, report)
            if self._llm is not None:
                try:
                    raw = self._llm(_SUMMARY_SYSTEM, context).strip()
                    title, _, body = raw.partition("\n")
                    report.title = title.strip()[:60]
                    report.summary = body.strip() or raw
                    continue
                except Exception:
                    logger.exception(
                        "community summary LLM failed for %s; using template",
                        report.community_id,
                    )
            report.title, report.summary = self._template_summary(index, report)
        return reports

    def _community_context(self, index: KnowledgeGraphIndex, report: CommunityReport) -> str:
        g = index.graph
        members = report.entity_ids[: self.max_members]
        lines = ["实体:"]
        for n in members:
            d = g.nodes[n]
            desc = d.get("description", "")
            lines.append(f"- {n} ({d.get('type', 'Entity')}): {desc[:120]}")
        lines.append("关系:")
        for a, b, d in g.subgraph(report.entity_ids).edges(data=True):
            lines.append(f"- {a} -[{sorted(d['types'])[0]}]-> {b} (weight={d['weight']:.2f})")
        return "\n".join(lines)

    def _template_summary(
        self, index: KnowledgeGraphIndex, report: CommunityReport
    ) -> tuple[str, str]:
        g = index.graph
        by_degree = sorted(
            report.entity_ids,
            key=lambda n: -g.degree(n, weight="weight"),
        )
        top = by_degree[:3]
        title = " / ".join(top)[:60]
        rel_bits = []
        sub = g.subgraph(report.entity_ids)
        for a, b, d in sorted(sub.edges(data=True), key=lambda e: -e[2]["weight"])[:5]:
            rel_bits.append(f"{a} -[{sorted(d['types'])[0]}]-> {b}")
        desc_bits = [
            f"{n}: {g.nodes[n].get('description', '')[:60]}"
            for n in top
            if g.nodes[n].get("description")
        ]
        summary = (
            f"该社区包含 {report.size} 个实体，核心实体为 {'、'.join(top)}。"
            + ("主要关系: " + "; ".join(rel_bits) + "。" if rel_bits else "")
            + (" ".join(desc_bits) if desc_bits else "")
        )
        return title, summary
