"""pytest 공용 픽스처."""

from types import SimpleNamespace

import pytest


def make_settings(**overrides) -> SimpleNamespace:
    """테스트용 Settings 대체. 어댑터/서비스가 참조하는 필드만 채운다."""
    base = dict(
        GRAPH_ENABLED=True,
        GRAPH_NEIGHBOR_LIMIT=30,
        GRAPH_CHUNK_LIMIT=20,
        GRAPH_COSINE_THRESHOLD=0.85,
        HTTP_TIMEOUT=30.0,
        POSTGRES_URL="",
        POSTGRES_USER="",
        POSTGRES_PASSWORD="",
        POSTGRES_SEARCH_PATH="rag,public",
        GLINER_URL="",
        GLINER_API_KEY="",
        QDRANT_URL="http://localhost:6333",
        ENTITY_COLLECTION="rag_graph_entities_v1",
        EMBEDDING_URL="",
        EMBEDDING_API_KEY="",
        EMBEDDING_MODEL="embed-bge-m3",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class FakePostgres:
    """PostgresAdapter 대체 — 인메모리 그래프."""

    def __init__(self, build_id=1, entities=None, neighbors=None, chunks=None):
        self._build_id = build_id
        self._entities = entities or {}       # normalized_name -> entity_id
        self._neighbors = neighbors or {}     # seed_id -> [neighbor_id]
        self._chunks = chunks or []           # rank_chunks 반환 행

    async def get_active_build_id(self):
        return self._build_id

    async def find_entity_by_name(self, build_id, normalized_name):
        return self._entities.get(normalized_name)

    async def expand_neighbors(self, build_id, seed_ids, limit):
        out = []
        for s in seed_ids:
            out.extend(self._neighbors.get(s, []))
        return out[:limit]

    async def rank_chunks_by_entities(self, build_id, seed_ids, candidate_ids, limit):
        return list(self._chunks)[:limit]

    async def close(self):
        pass


class FakeGliner:
    def __init__(self, entities):
        self._entities = entities  # list[{normalized, surface, type}]

    async def extract_entities(self, query):
        return list(self._entities)


class FakeEntityStore:
    def __init__(self, hits=None):
        self._hits = hits or []

    async def search_by_vector(self, query_vector, build_id, limit=1):
        return list(self._hits)[:limit]


class FakeEmbedding:
    def __init__(self, vector=None, raises=False):
        self._vector = vector or [0.1, 0.2, 0.3]
        self._raises = raises

    async def embed(self, text):
        if self._raises:
            raise RuntimeError("임베딩 실패")
        return list(self._vector)


@pytest.fixture
def settings():
    return make_settings()
