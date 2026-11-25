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
