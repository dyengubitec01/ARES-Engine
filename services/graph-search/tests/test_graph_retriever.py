"""GraphRetriever 3-Step 파이프라인 테스트 (스펙 §11 기반)."""

import pytest

from app.services.graph_retriever import GraphRetriever
from tests.conftest import (
    FakeEmbedding,
    FakeEntityStore,
    FakeGliner,
    FakePostgres,
    make_settings,
)

pytestmark = pytest.mark.asyncio


def build(settings=None, gliner=None, postgres=None, entity_store=None, embedding=None):
    return GraphRetriever(
        settings=settings or make_settings(),
        gliner=gliner or FakeGliner([]),
        postgres=postgres or FakePostgres(),
        entity_store=entity_store or FakeEntityStore(),
        embedding=embedding or FakeEmbedding(),
    )


async def test_graph_disabled_returns_empty():
    r = build(settings=make_settings(GRAPH_ENABLED=False))
    assert await r.retrieve("q") == []


async def test_no_active_build_returns_empty():
    r = build(postgres=FakePostgres(build_id=None))
    assert await r.retrieve("q") == []


async def test_no_entities_returns_empty():
    r = build(gliner=FakeGliner([]))
    assert await r.retrieve("q") == []


async def test_exact_match_seed_and_ranking():
    gliner = FakeGliner([{"normalized": "증평군", "surface": "증평군", "type": "LOC"}])
    postgres = FakePostgres(
        entities={"증평군": "e1"},
        neighbors={"e1": ["e2"]},
        chunks=[{
            "chunk_id": "c1", "content": "본문", "doc_content_id": "d1",
            "original_filename": "f.pdf", "score": 15.0, "hits": 3,
        }],
    )
    r = build(gliner=gliner, postgres=postgres)
    out = await r.retrieve("증평군 사업")
    assert len(out) == 1
    assert out[0]["chunk_id"] == "c1"
    assert out[0]["metadata"]["_source"] == "graph"
    assert out[0]["metadata"]["doc_id"] == "d1"


async def test_cosine_fallback_when_exact_miss():
    gliner = FakeGliner([{"normalized": "xx", "surface": "엔티티", "type": "ORG"}])
    postgres = FakePostgres(
        entities={},  # 정확 매칭 실패
        neighbors={"e9": []},
        chunks=[{
            "chunk_id": "c9", "content": "본문", "doc_content_id": "d9",
            "original_filename": "g.pdf", "score": 3.0, "hits": 1,
        }],
    )
    entity_store = FakeEntityStore(hits=[{"entity_id": "e9", "score": 0.9}])
    r = build(gliner=gliner, postgres=postgres, entity_store=entity_store)
    out = await r.retrieve("엔티티")
    assert out and out[0]["chunk_id"] == "c9"


async def test_embedding_failure_skips_entity():
    gliner = FakeGliner([{"normalized": "xx", "surface": "엔티티", "type": "ORG"}])
    r = build(
        gliner=gliner,
        postgres=FakePostgres(entities={}),
        embedding=FakeEmbedding(raises=True),
    )
    assert await r.retrieve("엔티티") == []


async def test_seed_dedup():
    gliner = FakeGliner([
        {"normalized": "a", "surface": "A", "type": "X"},
        {"normalized": "b", "surface": "B", "type": "X"},
    ])
    # 두 엔티티가 같은 entity_id로 매핑 → dedup 되어야 함
    postgres = FakePostgres(
        entities={"a": "same", "b": "same"},
        neighbors={"same": []},
        chunks=[{
            "chunk_id": "c", "content": "x", "doc_content_id": "d",
            "original_filename": "f", "score": 3.0, "hits": 1,
        }],
    )
    captured = {}
    orig = postgres.rank_chunks_by_entities

    async def spy(build_id, seed_ids, candidate_ids, limit):
        captured["seed_ids"] = seed_ids
        return await orig(build_id, seed_ids, candidate_ids, limit)

    postgres.rank_chunks_by_entities = spy
    r = build(gliner=gliner, postgres=postgres)
    await r.retrieve("A B")
    assert captured["seed_ids"] == ["same"]


async def test_fail_open_on_exception():
    class Boom(FakePostgres):
        async def get_active_build_id(self):
            raise RuntimeError("db down")

    r = build(postgres=Boom())
    assert await r.retrieve("q") == []
