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

        # search_path는 커넥션 시작 파라미터로 지정한다.
        # asyncpg 풀은 커넥션 반환 시 RESET ALL로 세션 설정을 초기화하는데,
        # init 콜백은 최초 1회만 실행되므로 SET search_path가 재획득 커넥션에서 사라진다.
        # server_settings로 넘기면 RESET ALL 후에도 시작값으로 유지된다.
        self._pool = await asyncpg.create_pool(
            dsn=self._url,
            user=self._user or None,
            password=self._password or None,
            min_size=1,
            max_size=5,
            command_timeout=self._timeout,
            server_settings={"search_path": self._search_path},
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
            # 공출현 강도(weight) 상위 이웃을 남긴다 (인수인계 md Step 2 · 스펙 §2 의도).
            # 이웃별 최대 weight로 집계 후 정렬해 중복 제거 + 강한 연결 우선.
            rows = await conn.fetch(
                "SELECT neighbor FROM ("
                "  SELECT (CASE "
                "    WHEN source_entity_id = ANY($1::uuid[]) THEN target_entity_id "
                "    ELSE source_entity_id END) AS neighbor, "
                "    MAX(weight) AS w "
                "  FROM rag_graph_edges "
                "  WHERE build_id = $2 "
                "    AND (source_entity_id = ANY($1::uuid[]) "
                "         OR target_entity_id = ANY($1::uuid[])) "
                "  GROUP BY neighbor "
                ") t "
                "ORDER BY w DESC LIMIT $3",
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
