# Graph-RAG 서버 — 신규 프로젝트 인수인계 스펙

> 이 문서는 **RAG-Search 서버에서 분리해 나가는 신규 Graph-RAG 서버**의 완전한 구축 스펙이다.
> 이 문서만 있으면 새 저장소에서 처음부터 구현·배포까지 가능하도록 설계했다.

---

## 0. 프로젝트 목적

- **역할**: 사용자 쿼리 → 그래프 기반 청크 회수(3-Step) → JSON 응답
- **역할 아님**: 벡터 검색, 리랭킹, LLM 답변 생성
- **위치**: agent 서버가 벡터 RAG(`rag-search`)와 이 그래프 서버(`rag-graph-search`)를 **각각 병렬 호출**하여 결과를 union → 리랭킹까지 agent 측에서 처리

```
사용자
  ↓
agent 서버
  ├→ POST /v1/search        → rag-search 서버   (벡터 축)
  └→ POST /v1/graph-search  → rag-graph-search 서버 (그래프 축) ← 이 프로젝트
  ↓
agent가 chunk_id로 union·dedup → 리랭커 호출 → LLM 답변
```

---

## 1. 배경 (결정 근거)

### 왜 지금 만드나

- 기존 RAG-Search 서버 안에 통합할 수도 있었으나, **팀 오너십·독립 스케일링·릴리즈 사이클 분리**를 위해 별도 서버로 분리.
- 그래프 로직은 이미 RAG-Search에 프로토타입됐고 (feat/graphrag-signal 브랜치), 그걸 이 프로젝트로 이관.

### 원장(experiments/LEDGER.md)이 확정한 것

| 항목 | 결론 |
|---|---|
| Union 방식 | chunk_id 기반 concat + dedup (RRF/interleave 아님) |
| 리랭커 처리 | union 풀에 태우면 유의미 (+0.018 uplift, distractor 코퍼스에서 확인) |
| always-on vs 조건부 | 현 운영 그래프(관계라벨 커버리지 18%)에선 성능 저하 → **default off** |
| 라벨 완주 목표 | 80%+ 시 judge +0.048 / recall +0.176 기대 |
| 커뮤니티축 | 이 빌드에선 무용, 제외 |

### GRAPH_ENABLED 기본값

- **dev: true** (개발·검증)
- **prod: false** (라벨 완주 신호 전까지)

---

## 2. 아키텍처

### 3-Step 파이프라인

```
POST /v1/graph-search
  {"query": "증평군 스마트도시 사업"}
    ↓
Step 0 — active build 고정
  SELECT id FROM rag_graph_builds WHERE status='active' ORDER BY id DESC LIMIT 1

Step 1 — 엔티티 링킹 (seed 찾기)
  ├─ GLiNER: 쿼리 → 엔티티 후보
  ├─ 각 후보 normalize(공백제거 + casefold)
  ├─ Postgres 정확 매칭 (normalized_name)
  └─ 실패 시 cosine fallback:
       BGE-M3로 surface 임베딩 → rag_graph_entities_v1 Qdrant 검색
       score >= 0.85 이면 seed 채택

Step 2 — 1-hop 이웃 확장
  SELECT ... FROM rag_graph_edges
  WHERE build_id=? AND (source IN seeds OR target IN seeds)
  ORDER BY weight DESC LIMIT 30

Step 3 — 청크 랭킹 (seed 3점, 이웃 1점)
  JOIN rag_graph_entity_chunks ec ← rag_chunks ch ← doc_document_content d
  WHERE ec.build_id=? AND ec.entity_id IN (seeds ∪ neighbors)
  GROUP BY chunk_id
  ORDER BY score DESC, hits DESC LIMIT 20
    ↓
JSON 응답 (chunk_id, content, metadata, score, _source="graph")
```

### 계층

```
[API Layer]           routes.py           POST /v1/graph-search
[Service Layer]       graph_retriever.py  3-Step 조율
[Adapter Layer]       postgres_adapter.py
                      gliner_adapter.py
                      entity_qdrant_adapter.py
                      embedding_adapter.py  (surface 임베딩 fallback)
[External Systems]    Postgres · GLiNER · Qdrant · 임베딩 서버
```

---

## 3. API 계약

### 요청

```
POST /v1/graph-search
Content-Type: application/json
X-LF-Trace-ID: <optional>   # agent 서버가 시작한 trace 승계
X-LF-Parent-Id: <optional>

{
  "query": "증평군 스마트도시 사업",
  "excluded_docs": [],             // optional
  "chunk_limit": 20                // optional, default 설정값
}
```

### 응답 (성공)

```json
{
  "code": "RAG100000",
  "msg": "그래프 검색 성공",
  "data": {
    "query": "증평군 스마트도시 사업",
    "trace_id": "abc123...",
    "results": [
      {
        "rank": 1,
        "chunk_id": "chunk-uuid",
        "content": "본문 텍스트",
        "metadata": {
          "doc_id": "doc-content-uuid",
          "original_filename": "example.pdf",
          "_source": "graph"
        },
        "score": 15.0,
        "hits": 3
      }
    ]
  }
}
```

### 응답 (결과 없음)

```json
{
  "code": "RAG100001",
  "msg": "검색 결과 없음"
}
```

### 응답 (실패, fail-open으로 대부분 발생 안 함)

```json
{
  "code": "RAG100060",
  "msg": "그래프 저장소 연동 실패"
}
```

**Fail-open 원칙**: 내부 예외는 모두 흡수하고 빈 결과 반환. agent 서버가 벡터 축만으로 계속 진행 가능하도록.

---

## 4. 프로젝트 구조

```
rag-graph-search/
├── app/
│   ├── __init__.py
│   ├── main.py                    FastAPI 팩토리, DI, 예외 핸들러
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              POST /v1/graph-search
│   │   └── responses.py           RAGCode, APIResponse
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py              Settings (env)
│   │   ├── interfaces.py          GraphRetrieverInterface, EmbeddingInterface
│   │   ├── exceptions.py          RAGBaseException 계층
│   │   └── monitoring.py          Langfuse 미들웨어
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── postgres_adapter.py    Postgres access (3-Step 쿼리 4개)
│   │   ├── gliner_adapter.py      GLiNER 엔티티 추출
│   │   ├── entity_qdrant_adapter.py  엔티티 벡터 검색
│   │   ├── embedding_adapter.py   BGE-M3 임베딩 (fallback용)
│   │   └── mocks/
│   │       ├── __init__.py
│   │       └── mock_graph_retriever.py
│   └── services/
│       ├── __init__.py
│       └── graph_retriever.py     3-Step 조립
├── tests/
│   ├── conftest.py
│   ├── test_graph_retriever.py
│   ├── test_postgres_adapter.py
│   ├── test_gliner_adapter.py
│   └── test_entity_qdrant_adapter.py
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── Jenkinsfile
├── pyproject.toml
├── .env.example
└── README.md
```

---

## 5. Config

`.env.example`:

```bash
# --- App ---
APP_ENV=dev
APP_HOST=0.0.0.0
APP_PORT=8007                        # rag-search는 8006, 이 서버는 8007
LOG_LEVEL=DEBUG

# --- Graph-RAG Flag ---
GRAPH_ENABLED=true                   # dev만 true, prod는 false

# --- Postgres (Graph DB) ---
POSTGRES_URL=postgresql://localhost:5432/ragdb_dev
POSTGRES_USER=raguser
POSTGRES_PASSWORD=                   # 원본 그대로 (URL 인코딩 불필요)
POSTGRES_SEARCH_PATH=rag_dev,public

# --- GLiNER Entity Extraction ---
GLINER_URL=http://localhost:8001/extract
GLINER_API_KEY=                      # Bearer 토큰

# --- Qdrant (엔티티 벡터 컬렉션) ---
QDRANT_URL=http://localhost:6333
ENTITY_COLLECTION=rag_graph_entities_v1_dev

# --- Embedding API (fallback surface 임베딩) ---
# BGE-M3 (OpenAI-compatible)
EMBEDDING_URL=http://localhost:4000/v1/embeddings
EMBEDDING_API_KEY=
EMBEDDING_MODEL=embed-bge-m3

# --- Graph-RAG 튜닝 ---
GRAPH_COSINE_THRESHOLD=0.85          # 엔티티 링킹 fallback 임계값
GRAPH_NEIGHBOR_LIMIT=30              # 1-hop 이웃 최대
GRAPH_CHUNK_LIMIT=20                 # 응답 청크 최대

# --- Langfuse ---
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# --- HTTP ---
HTTP_TIMEOUT=30.0
```

⚠️ **시크릿은 반드시 Jenkins credential(`env-rag-graph-search-dev` / `env-rag-graph-search`)로 관리. 이 문서에 평문 넣지 말 것.**

---

## 6. 데이터 계약

### PostgreSQL 스키마 (읽기 전용, SELECT만)

인덱싱팀이 관리. 이 서버는 조회만.

| 테이블 | 사용 컬럼 |
|---|---|
| `rag_graph_builds` | `id`, `status` (active/superseded/failed/building) |
| `rag_graph_entities` | `id`, `build_id`, `name`, `normalized_name`, `entity_type` |
| `rag_graph_entity_chunks` | `entity_id`, `chunk_id`, `doc_content_id`, `build_id`, `occurrence_count` |
| `rag_graph_edges` | `source_entity_id`, `target_entity_id`, `build_id`, `weight`, `relation_label` |
| `rag_chunks` | `id`, `text`, `doc_content_id` (본문 조인용) |
| `doc_document_content` | `id`, `original_filename` (파일명 조인용) |

### Qdrant 컬렉션 `rag_graph_entities_v1`

- `point_id` = 엔티티 UUID (= `rag_graph_entities.id`)
- `payload`: `{entity_id, build_id, name, entity_type, normalized_name}`
- 벡터: BGE-M3 dense, 1024-dim, cosine
- **`build_id` 필터 필수** (구 빌드 GC 방어)

### 정규화 규칙 (필수 일치)

```python
def normalize(name: str) -> str:
    """공백 전부 제거 + casefold. Postgres normalized_name과 반드시 동일."""
    return re.sub(r"\s+", "", (name or "").strip()).casefold()
```

---

## 7. 소스 코드 (그대로 복사·이관)

이 코드들은 이미 RAG-Search feat/graphrag-signal 브랜치에서 검증됨. 그대로 새 프로젝트에 옮기고, `app.` 임포트 경로만 확인하면 됨.

### `app/core/interfaces.py`

```python
"""벡터 스토어, 리랭커, 임베딩 추상 인터페이스."""

from abc import ABC, abstractmethod


class GraphRetrieverInterface(ABC):
    """그래프 기반 청크 회수 어댑터 인터페이스.

    Fail-open 원칙: 실패 시 반드시 빈 리스트를 반환한다.
    """

    @abstractmethod
    async def retrieve(self, query: str) -> list[dict]:
        """query로 그래프 축 후보 청크를 회수한다.

        Returns:
            {chunk_id, content, metadata, score, _source="graph"} 리스트.
            실패·비활성화 시 빈 리스트.
        """


class EmbeddingInterface(ABC):
    """임베딩 어댑터 인터페이스."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """텍스트를 벡터로 변환한다."""
```

### `app/adapters/postgres_adapter.py`

```python
"""PostgreSQL 어댑터 — Graph-RAG 그래프 저장소 접근."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)


class PostgresAdapter:
    """Graph-RAG PostgreSQL 접근 어댑터."""

    def __init__(self, settings: Settings) -> None:
        self._url = settings.POSTGRES_URL
        self._user = settings.POSTGRES_USER
        self._password = settings.POSTGRES_PASSWORD
        self._search_path = settings.POSTGRES_SEARCH_PATH
        self._timeout = settings.HTTP_TIMEOUT
        self._pool: "asyncpg.Pool | None" = None

    async def _ensure_pool(self) -> "asyncpg.Pool":
        if self._pool is not None:
            return self._pool

        import asyncpg

        async def _init_conn(conn: "asyncpg.Connection") -> None:
            await conn.execute(f"SET search_path TO {self._search_path}")

        self._pool = await asyncpg.create_pool(
            dsn=self._url,
            user=self._user or None,
            password=self._password or None,
            min_size=1,
            max_size=5,
            command_timeout=self._timeout,
            init=_init_conn,
        )
        logger.info("PostgreSQL 풀 초기화 완료: search_path=%s", self._search_path)
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def get_active_build_id(self) -> int | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM rag_graph_builds "
                "WHERE status = 'active' ORDER BY id DESC LIMIT 1"
            )
        return int(row["id"]) if row else None

    async def find_entity_by_name(
        self, build_id: int, normalized_name: str
    ) -> str | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM rag_graph_entities "
                "WHERE build_id = $1 AND normalized_name = $2 LIMIT 1",
                build_id, normalized_name,
            )
        return str(row["id"]) if row else None

    async def expand_neighbors(
        self, build_id: int, seed_ids: list[str], limit: int
    ) -> list[str]:
        if not seed_ids:
            return []
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT (CASE "
                "  WHEN source_entity_id = ANY($1::uuid[]) THEN target_entity_id "
                "  ELSE source_entity_id END) AS neighbor "
                "FROM rag_graph_edges "
                "WHERE build_id = $2 "
                "  AND (source_entity_id = ANY($1::uuid[]) "
                "       OR target_entity_id = ANY($1::uuid[])) "
                "ORDER BY neighbor LIMIT $3",
                seed_ids, build_id, limit,
            )
        return [str(r["neighbor"]) for r in rows]

    async def rank_chunks_by_entities(
        self, build_id: int, seed_ids: list[str],
        candidate_ids: list[str], limit: int,
    ) -> list[dict]:
        if not candidate_ids:
            return []
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ec.chunk_id, ch.text AS content, "
                "       ch.doc_content_id, d.original_filename, "
                "       SUM(CASE WHEN ec.entity_id = ANY($1::uuid[]) THEN 3 ELSE 1 END) AS score, "
                "       COUNT(*) AS hits "
                "FROM rag_graph_entity_chunks ec "
                "JOIN rag_chunks ch          ON ec.chunk_id = ch.id "
                "JOIN doc_document_content d ON ch.doc_content_id = d.id "
                "WHERE ec.build_id = $2 AND ec.entity_id = ANY($3::uuid[]) "
                "GROUP BY ec.chunk_id, ch.text, ch.doc_content_id, d.original_filename "
                "ORDER BY score DESC, hits DESC LIMIT $4",
                seed_ids, build_id, candidate_ids, limit,
            )
        return [
            {
                "chunk_id": str(r["chunk_id"]),
                "content": r["content"] or "",
                "doc_content_id": str(r["doc_content_id"]),
                "original_filename": r["original_filename"] or "",
                "score": float(r["score"]),
                "hits": int(r["hits"]),
            }
            for r in rows
        ]
```

### `app/adapters/gliner_adapter.py`

```python
r"""GLiNER2 엔티티 추출 API 어댑터."""

import logging
import re

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

_QUERY_BOUNDARY_RE = re.compile(r"[_/\\]+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_entity_name(name: str) -> str:
    """공백 제거 + casefold. Postgres 저장 규칙과 동일해야 함."""
    return _WHITESPACE_RE.sub("", (name or "").strip()).casefold()


class GLinerAdapter:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.GLINER_URL
        self._api_key = settings.GLINER_API_KEY
        self._timeout = settings.HTTP_TIMEOUT

    async def extract_entities(self, query: str) -> list[dict]:
        """{normalized, surface, type} 리스트. 실패 시 상위에서 흡수."""
        cleaned = _QUERY_BOUNDARY_RE.sub(" ", query)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._url,
                json={"texts": [cleaned]},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results") or []
        if not results:
            return []
        entities = results[0].get("entities") or []

        out, seen = [], set()
        for e in entities:
            surface = e.get("name") or ""
            if not surface:
                continue
            norm = normalize_entity_name(surface)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            out.append({
                "normalized": norm,
                "surface": surface,
                "type": e.get("type") or "",
            })
        return out
```

### `app/adapters/entity_qdrant_adapter.py`

```python
"""엔티티 벡터 검색 어댑터 — Step 1 cosine fallback."""

import logging

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EntityQdrantAdapter:
    def __init__(self, settings: Settings) -> None:
        self._client = AsyncQdrantClient(url=settings.QDRANT_URL)
        self._collection_name = settings.ENTITY_COLLECTION
        self._cosine_threshold = settings.GRAPH_COSINE_THRESHOLD

    async def search_by_vector(
        self, query_vector: list[float], build_id: int, limit: int = 1,
    ) -> list[dict]:
        try:
            query_filter = Filter(
                must=[FieldCondition(key="build_id", match=MatchValue(value=build_id))]
            )
            results = await self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,
                limit=limit,
                query_filter=query_filter,
                score_threshold=self._cosine_threshold,
            )
            return [
                {
                    "entity_id": p.payload.get("entity_id"),
                    "name": p.payload.get("name", ""),
                    "normalized_name": p.payload.get("normalized_name", ""),
                    "score": p.score,
                }
                for p in results.points
                if p.payload.get("entity_id")
            ]
        except (UnexpectedResponse, httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning("엔티티 벡터 검색 실패: %s", exc)
            return []
        except (KeyError, AttributeError) as exc:
            logger.warning("엔티티 벡터 응답 파싱 실패: %s", exc)
            return []
```

### `app/adapters/embedding_adapter.py`

```python
"""BGE-M3 임베딩 어댑터 (OpenAI-compatible).

엔티티 링킹 cosine fallback에서 surface 임베딩용으로만 호출된다.
"""

import logging

import httpx

from app.core.config import Settings
from app.core.interfaces import EmbeddingInterface

logger = logging.getLogger(__name__)


class EmbeddingAdapter(EmbeddingInterface):
    def __init__(self, settings: Settings) -> None:
        self._url = settings.EMBEDDING_URL
        self._api_key = settings.EMBEDDING_API_KEY
        self._model = settings.EMBEDDING_MODEL
        self._timeout = settings.HTTP_TIMEOUT

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._url,
                json={"model": self._model, "input": [text]},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            data = response.json()
        # index 순 정렬 (실질적으로 하나뿐)
        items = sorted(data["data"], key=lambda x: x["index"])
        return items[0]["embedding"]
```

### `app/services/graph_retriever.py`

```python
"""Graph-RAG 3-Step 조회 조율 서비스."""

import logging

from app.adapters.entity_qdrant_adapter import EntityQdrantAdapter
from app.adapters.gliner_adapter import GLinerAdapter
from app.adapters.postgres_adapter import PostgresAdapter
from app.core.config import Settings
from app.core.interfaces import EmbeddingInterface, GraphRetrieverInterface

logger = logging.getLogger(__name__)


class GraphRetriever(GraphRetrieverInterface):
    def __init__(
        self,
        settings: Settings,
        gliner: GLinerAdapter,
        postgres: PostgresAdapter,
        entity_store: EntityQdrantAdapter,
        embedding: EmbeddingInterface,
    ) -> None:
        self._settings = settings
        self._gliner = gliner
        self._postgres = postgres
        self._entity_store = entity_store
        self._embedding = embedding

    async def retrieve(self, query: str) -> list[dict]:
        if not self._settings.GRAPH_ENABLED:
            return []
        try:
            build_id = await self._postgres.get_active_build_id()
            if build_id is None:
                logger.warning("Graph-RAG: active build 없음 — 스킵")
                return []

            seed_ids = await self._link_seeds(build_id, query)
            if not seed_ids:
                return []

            neighbors = await self._postgres.expand_neighbors(
                build_id, seed_ids, limit=self._settings.GRAPH_NEIGHBOR_LIMIT,
            )
            candidates = list({*seed_ids, *neighbors})

            rows = await self._postgres.rank_chunks_by_entities(
                build_id=build_id,
                seed_ids=seed_ids,
                candidate_ids=candidates,
                limit=self._settings.GRAPH_CHUNK_LIMIT,
            )
            return [self._to_result(r) for r in rows]

        except Exception as exc:
            logger.warning("Graph-RAG 파이프라인 실패 — 빈 결과: %s", exc)
            return []

    async def _link_seeds(self, build_id: int, query: str) -> list[str]:
        entities = await self._gliner.extract_entities(query)
        if not entities:
            return []

        seeds, seen = [], set()
        for ent in entities:
            entity_id = await self._postgres.find_entity_by_name(
                build_id, ent["normalized"]
            )
            if entity_id is None:
                try:
                    surface_vec = await self._embedding.embed(ent["surface"])
                except Exception as exc:
                    logger.warning("surface 임베딩 실패 skip: %s", exc)
                    continue
                hits = await self._entity_store.search_by_vector(
                    query_vector=surface_vec, build_id=build_id, limit=1,
                )
                if not hits:
                    continue
                entity_id = str(hits[0]["entity_id"])

            if entity_id and entity_id not in seen:
                seen.add(entity_id)
                seeds.append(entity_id)
        return seeds

    @staticmethod
    def _to_result(row: dict) -> dict:
        return {
            "chunk_id": row["chunk_id"],
            "content": row["content"],
            "metadata": {
                "doc_id": row.get("doc_content_id", ""),
                "original_filename": row.get("original_filename", ""),
                "_source": "graph",
            },
            "score": row.get("score", 0.0),
            "hits": row.get("hits", 0),
        }
```

### `app/api/routes.py`

```python
"""API 라우터 - 그래프 검색 엔드포인트."""

import uuid
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.responses import no_result_response, success_response
from app.core.config import get_settings
from app.core.exceptions import BadRequestException

router = APIRouter(prefix="/v1", tags=["graph-search"])


class GraphSearchRequest(BaseModel):
    query: str
    excluded_docs: list[str] = []
    chunk_limit: Optional[int] = None


@router.post("/graph-search")
async def graph_search(body: GraphSearchRequest, request: Request) -> dict:
    if not body.query.strip():
        raise BadRequestException(msg="잘못된 요청: query는 빈 문자열일 수 없습니다")

    graph_retriever = request.app.state.graph_retriever
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    results = await graph_retriever.retrieve(body.query)

    if body.excluded_docs:
        excluded = set(body.excluded_docs)
        results = [
            r for r in results
            if r["metadata"].get("doc_id") not in excluded
        ]

    if not results:
        return no_result_response()

    # rank 부여
    for rank, r in enumerate(results, start=1):
        r["rank"] = rank

    return success_response(data={
        "query": body.query,
        "trace_id": trace_id,
        "results": results,
    })
```

### `app/api/responses.py`

RAG-Search 서버의 `responses.py`를 그대로 복사. 다만 `SEARCH_SUCCESS` msg를 "그래프 검색 성공"으로 바꾸면 좋음.

### `app/core/config.py`

```python
import os
from functools import lru_cache

from pydantic_settings import BaseSettings

TRACE_ID_HEADER = "X-LF-Trace-ID"
PARENT_ID_HEADER = "X-LF-Parent-Id"

_APP_ENV = os.getenv("APP_ENV", "dev")


class Settings(BaseSettings):
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8007
    LOG_LEVEL: str = "DEBUG"

    # Graph flag
    GRAPH_ENABLED: bool = False

    # Postgres
    POSTGRES_URL: str = ""
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_SEARCH_PATH: str = "rag,public"

    # GLiNER
    GLINER_URL: str = ""
    GLINER_API_KEY: str = ""

    # Qdrant (entity)
    QDRANT_URL: str = "http://localhost:6333"
    ENTITY_COLLECTION: str = "rag_graph_entities_v1"

    # Embedding
    EMBEDDING_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "embed-bge-m3"

    # Tuning
    GRAPH_COSINE_THRESHOLD: float = 0.85
    GRAPH_NEIGHBOR_LIMIT: int = 30
    GRAPH_CHUNK_LIMIT: int = 20

    # Langfuse
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # HTTP
    HTTP_TIMEOUT: float = 30.0

    model_config = {
        "env_file": f".env.{_APP_ENV}",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### `app/main.py` (핵심 부분만)

```python
def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.DEBUG),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from app.adapters.embedding_adapter import EmbeddingAdapter
    from app.adapters.entity_qdrant_adapter import EntityQdrantAdapter
    from app.adapters.gliner_adapter import GLinerAdapter
    from app.adapters.postgres_adapter import PostgresAdapter
    from app.services.graph_retriever import GraphRetriever

    embedding = EmbeddingAdapter(settings)
    postgres = PostgresAdapter(settings)
    graph_retriever = GraphRetriever(
        settings=settings,
        gliner=GLinerAdapter(settings),
        postgres=postgres,
        entity_store=EntityQdrantAdapter(settings),
        embedding=embedding,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await postgres.close()
        shutdown_langfuse()

    app = FastAPI(title="RAG Graph Search Server", lifespan=lifespan)
    app.state.graph_retriever = graph_retriever
    langfuse_client = get_langfuse_client()
    app.add_middleware(LangfuseMiddleware, langfuse_client=langfuse_client)
    app.include_router(router)

    # 예외 핸들러: RAG-Search와 동일 패턴 복사
    # /health 엔드포인트: RAG-Search와 동일

    return app
```

### `app/adapters/mocks/mock_graph_retriever.py` · 테스트 코드

RAG-Search feat/graphrag-signal 브랜치의 파일 그대로 복사:
- `app/adapters/mocks/mock_graph_retriever.py`
- `tests/test_graph_retriever.py`

---

## 8. `pyproject.toml`

```toml
[project]
name = "rag-graph-search-server"
version = "0.1.0"
description = "Graph-RAG Search Server — 엔티티 그래프 기반 청크 회수"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.104.0,<1.0.0",
    "uvicorn[standard]>=0.24.0,<1.0.0",
    "pydantic>=2.0,<3.0",
    "pydantic-settings>=2.0,<3.0",
    "httpx>=0.25.0,<1.0.0",
    "python-dotenv>=1.0.0,<2.0.0",
    "langfuse>=3.8.0,<4.0.0",
    "qdrant-client>=1.12.0,<2.0.0",
    "asyncpg>=0.29.0,<1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0,<9.0",
    "pytest-asyncio>=0.21,<1.0",
    "httpx",
]
```

---

## 9. Docker

### `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --no-cache-dir -e .

EXPOSE 8007

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]
```

### `docker-compose.yml` (prod)

```yaml
services:
  rag-graph-search:
    image: registry.example.com/ares/rag-graph-search:latest
    container_name: rag-graph-search
    ports:
      - "${PORT:-8007}:8007"
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    command: ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8007 2>&1 | tee -a /app/logs/app.log"]
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "10"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8007/health"]
      interval: 30s
      timeout: 5s
      start_period: 10s
      retries: 3
```

### `docker-compose.dev.yml`

포트만 8507로 바꿔서 동일하게 구성.

---

## 10. Jenkinsfile

RAG-Search Jenkinsfile을 그대로 참고. 다만:
- `IMAGE_NAME = 'rag-graph-search'`
- `ENV_CREDENTIALS = isProd ? 'env-rag-graph-search' : 'env-rag-graph-search-dev'` (신규 credential 생성 필요)
- `DEPLOY_PATH`: `/home/ubuntu/rag-graph-search{-dev}/compose`
- `COMPOSE_PROJECT`: `rag-graph-search{-dev}`

---

## 11. 테스트 계획

RAG-Search에서 이미 검증된 19개 테스트를 그대로 복사:
- `tests/test_graph_retriever.py`
  - GRAPH_ENABLED off, active build 없음, 정확매칭, cosine fallback, seed dedup, 전체 파이프라인, fail-open 등

추가 필요:
- `tests/test_routes.py` — `/v1/graph-search` 엔드포인트 통합 테스트
- `tests/test_health.py` — 헬스체크
- `tests/test_main_startup.py` — DI 배선

---

## 12. 배포 체크리스트

- [ ] 저장소 생성 (`rag-graph-search`)
- [ ] 위 파일 구조로 코드 이관
- [ ] Jenkins credential 2개 생성 (`env-rag-graph-search-dev`, `env-rag-graph-search`)
  - dev credential에 `GRAPH_ENABLED=true` + 실제 시크릿
  - prod credential에 `GRAPH_ENABLED=false` (완주 전까지)
- [ ] 사내 Docker 레지스트리 저장소 준비 (`registry.example.com/ares/rag-graph-search`)
- [ ] 배포 서버(localhost)에 `/home/ubuntu/rag-graph-search-dev/compose` 디렉터리 준비
- [ ] Jenkins pipeline 등록
- [ ] develop 브랜치 첫 배포 후 `curl http://localhost:8507/health` 확인
- [ ] `POST /v1/graph-search` smoke test
- [ ] Langfuse trace 확인

---

## 13. agent 서버 협의 사항

이 서버가 뜨면 agent 서버는 다음을 해야 함:

1. **병렬 호출**
   ```python
   vec_res, graph_res = await asyncio.gather(
       call_rag_search(query),
       call_rag_graph_search(query),
   )
   ```

2. **chunk_id union·dedup**
   - 벡터축 payload의 `chunk_id` ↔ 그래프축 응답의 `chunk_id` 매칭
   - 겹치면 `_source: "both"` 표기
   
3. **리랭커 호출** — 합쳐진 풀을 태움 (원장 결론)

4. **Fail-open 존중** — 그래프 서버가 빈 배열/에러 응답해도 벡터축만으로 계속 진행

5. **Trace 승계** — `X-LF-Trace-ID`, `X-LF-Parent-Id` 헤더 전달

---

## 14. 완주 신호 관리

라벨 커버리지가 80%+ 도달하면:
- 그래프팀에서 신호
- prod credential의 `GRAPH_ENABLED`를 `true`로 변경
- 컨테이너 재시작
- Langfuse trace에서 graph-retrieval span 응답 확인
- 골든셋 재현율·judge 지표 재측정

---

## 15. 참고 자료

- RAG-Search 서버 저장소: `feat/graphrag-signal` 브랜치 — 이 스펙의 원본 코드가 여기 있음
- 원장(LEDGER): 인덱싱팀 저장소 `experiments/LEDGER.md` — 성능 실측 근거
- 인수인계 md 원본: `GraphRAG_검색단_인수인계.md` — 초기 설계 (일부는 원장으로 재해석됨)

---

## 문서 종료

이 문서를 새 저장소 루트에 `docs/PROJECT_SPEC.md` 또는 `README.md`로 두고 시작하면 됨. 코드 이관 시 `app.` 임포트 경로만 확인.
