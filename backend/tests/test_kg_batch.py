"""Verify KnowledgeGraphService.ingest_knowledge groups by label / rel_type
and issues a single UNWIND query per group instead of one session per row.

以前 每个实体/关系一个 session，大批量入图时性能雪崩。批处理后应该只为每个
label / rel_type 开一个 session，并用 UNWIND 一次性写入全部同类型的行。
这里用 mock driver 验证分组、session 调用次数以及 cypher 中含 UNWIND。
"""
from unittest.mock import MagicMock

from app.services.kg_service import KnowledgeGraphService


def _make_svc_with_mock_driver(cnt: int = 1) -> KnowledgeGraphService:
    svc = KnowledgeGraphService()
    svc.driver = MagicMock()
    session = svc.driver.session.return_value.__enter__.return_value
    session.run.return_value.single.return_value = {"cnt": cnt}
    return svc


def _session_of(svc: KnowledgeGraphService):
    return svc.driver.session.return_value.__enter__.return_value


def test_ingest_knowledge_groups_entities_by_label():
    svc = _make_svc_with_mock_driver(cnt=10)
    session = _session_of(svc)

    entities = [
        {"name": "FAISS", "type": "Technology", "confidence": 0.9},
        {"name": "Neo4j", "type": "Technology", "confidence": 0.95},
        {"name": "OpenAI", "type": "Organization", "confidence": 0.8},
    ]

    stats = svc.ingest_knowledge(entities=entities, relations=[])

    # 2 labels = 2 session.run 调用
    assert session.run.call_count == 2, \
        f"期望每个 label 一个 session.run，实际 {session.run.call_count}"

    queries = [c.args[0] for c in session.run.call_args_list]
    assert all("UNWIND $rows AS row" in q for q in queries), \
        "所有实体批处理查询都应使用 UNWIND"

    # 一组 2 行（Technology），一组 1 行（Organization）
    sizes = sorted(len(c.kwargs["rows"]) for c in session.run.call_args_list)
    assert sizes == [1, 2]

    assert stats["entities_created"] == 2 * 10  # 2 组 * cnt=10


def test_ingest_knowledge_groups_relations_by_type():
    svc = _make_svc_with_mock_driver(cnt=5)
    session = _session_of(svc)

    relations = [
        {"source": "A", "target": "B", "type": "USES"},
        {"source": "B", "target": "C", "type": "USES"},
        {"source": "A", "target": "C", "type": "DEPENDS_ON"},
    ]

    stats = svc.ingest_knowledge(entities=[], relations=relations)

    assert session.run.call_count == 2, \
        f"期望每个 rel_type 一个 session.run，实际 {session.run.call_count}"

    queries = [c.args[0] for c in session.run.call_args_list]
    assert all("UNWIND $rows AS row" in q for q in queries)

    sizes = sorted(len(c.kwargs["rows"]) for c in session.run.call_args_list)
    assert sizes == [1, 2]

    assert stats["relations_created"] == 2 * 5


def test_ingest_knowledge_skips_missing_names():
    svc = _make_svc_with_mock_driver(cnt=0)
    session = _session_of(svc)

    entities = [
        {"name": "", "type": "Technology"},
        {"type": "Technology"},  # missing name
    ]
    relations = [
        {"source": "A", "target": "", "type": "USES"},
        {"source": "", "target": "B", "type": "USES"},
    ]

    stats = svc.ingest_knowledge(entities=entities, relations=relations)

    # 全部被过滤，不应该开启任何 session
    assert session.run.call_count == 0
    assert stats == {"entities_created": 0, "relations_created": 0}


def test_ingest_knowledge_no_driver_returns_zero_stats():
    svc = KnowledgeGraphService()
    svc.driver = None

    stats = svc.ingest_knowledge(
        entities=[{"name": "x", "type": "Technology"}],
        relations=[{"source": "x", "target": "y", "type": "USES"}],
    )
    assert stats == {"entities_created": 0, "relations_created": 0}
