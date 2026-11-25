"""Qdrant 벡터 검색 어댑터.

payload 구조:
  - QDRANT_CONTENT_FIELD(기본값 "text_for_search")로 지정된 필드를 본문 텍스트로 추출
  - 나머지 필드(doc_content_id, chunk_id, original_filename 등)는 metadata로 추출

반환 dict에는 Qdrant point.id를 `_point_id`로 함께 담는다(RRF 중복 판별 키).
언더스코어 필드는 응답 직전 제거한다.
"""

import asyncio
import logging

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchText,
    MatchValue,
)

from app.core.config import Settings
from app.core.exceptions import VectorStoreException
from app.core.interfaces import VectorStoreInterface
from app.core.payload_fields import PayloadField

logger = logging.getLogger(__name__)

# parent 회수 scroll 페이지 크기 (한 번에 가져올 최대 청크 수)
_SCROLL_BATCH = 256


class QdrantAdapter(VectorStoreInterface):
    """Qdrant 벡터 DB에서 유사 문서를 검색한다.

    AsyncQdrantClient를 사용하여 비동기로 query_points 호출.
    """

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncQdrantClient(url=settings.QDRANT_URL)
        self._collection_name = settings.QDRANT_COLLECTION
        self._content_field = settings.QDRANT_CONTENT_FIELD

    def _build_query_filter(
        self,
        excluded_docs: list[str] | None,
    ) -> Filter:
        """dense/BM25 검색이 공유하는 활성·제외 필터를 구성한다.

        부서(auth_dept_id) 필터는 정책 결정에 따라 적용하지 않는다 — 전 부서 검색 개방.
        """
        must = [
            FieldCondition(
                key=PayloadField.IS_ACTIVE,
                match=MatchValue(value="Y"),
            ),
        ]
        must_not = []
        if excluded_docs:
            must_not.append(
                FieldCondition(
                    key=PayloadField.DOC_CONTENT_ID,
                    match=MatchAny(any=excluded_docs),
                )
            )
        return Filter(must=must, must_not=must_not or None)

    def _point_to_dict(self, point) -> dict:
        """Qdrant point 객체를 표준 반환 dict로 변환한다."""
        return {
            "content": point.payload.get(self._content_field, ""),
            "metadata": {
                k: v
                for k, v in point.payload.items()
                if k != self._content_field
            },
            "score": point.score,
            "_point_id": point.id,
        }

    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        user_depts: list[str],
        excluded_docs: list[str] | None = None,
    ) -> list[dict]:
        """벡터 유사도 검색을 수행한다.

        Args:
            query_vector: 쿼리 임베딩 벡터.
            top_k: 반환할 최대 결과 수.
            user_depts: 부서 UUID 리스트. 검색 필터에는 사용하지 않는다(부서 필터 개방) — 로깅·모니터링 목적으로만 전달된다.
            excluded_docs: 제외할 doc_content_id 리스트.

        Returns:
            검색 결과 리스트. 각 항목은 content, metadata, score, _point_id를 포함한다.
            결과가 없으면 빈 리스트를 반환한다.

        Raises:
            VectorStoreException: Qdrant 연결/검색 실패 시.
        """
        try:
            logger.info(
                "Qdrant 검색: collection=%s user_depts(필터 미적용)=%s excluded_docs=%s",
                self._collection_name, user_depts, excluded_docs or [],
            )
            query_filter = self._build_query_filter(excluded_docs)
            results = await self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,
                limit=top_k,
                query_filter=query_filter,
            )
            return [self._point_to_dict(point) for point in results.points]
        except UnexpectedResponse as exc:
            logger.error(
                "Qdrant 검색 에러: collection=%s status=%s",
                self._collection_name,
                getattr(exc, "status_code", "unknown"),
            )
            raise VectorStoreException(
                msg=f"Qdrant 검색 에러: {exc}"
            ) from exc
        except httpx.ConnectError as exc:
            logger.error(
                "Qdrant 연결 실패: collection=%s",
                self._collection_name,
            )
            raise VectorStoreException(
                msg=f"Qdrant 연결 실패: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            logger.error(
                "Qdrant 요청 타임아웃: collection=%s",
                self._collection_name,
            )
            raise VectorStoreException(
                msg=f"Qdrant 요청 타임아웃: {exc}"
            ) from exc
        except (KeyError, AttributeError) as exc:
            logger.error(
                "Qdrant 응답 파싱 실패: collection=%s",
                self._collection_name,
            )
            raise VectorStoreException(
                msg=f"Qdrant 응답 파싱 실패: {exc}"
            ) from exc

    async def text_search(
        self,
        query_text: str,
        top_k: int,
        user_depts: list[str],
        excluded_docs: list[str] | None = None,
    ) -> list[dict]:
        """BM25 기반 full-text 검색을 수행한다.

        text_for_search 필드에 생성된 Qdrant full-text index 기반으로
        쿼리 텍스트를 매칭한다. 벡터를 사용하지 않는다.

        Args:
            query_text: 검색 쿼리 문자열.
            top_k: 반환할 최대 결과 수.
            user_depts: 부서 UUID 리스트. 검색 필터에는 사용하지 않는다(부서 필터 개방) — 로깅·모니터링 목적으로만 전달된다.
            excluded_docs: 제외할 doc_content_id 리스트.

        Returns:
            검색 결과 리스트. 각 항목은 content, metadata, score, _point_id를 포함한다.
            결과가 없으면 빈 리스트를 반환한다.

        Raises:
            VectorStoreException: Qdrant 연결/검색 실패 시.
        """
        try:
            logger.info(
                "Qdrant BM25 검색: collection=%s user_depts(필터 미적용)=%s excluded_docs=%s",
                self._collection_name, user_depts, excluded_docs or [],
            )
            base_filter = self._build_query_filter(excluded_docs)
            text_condition = FieldCondition(
                key=self._content_field,
                match=MatchText(text=query_text),
            )
            bm25_filter = Filter(
                must=(base_filter.must or []) + [text_condition],
                must_not=base_filter.must_not,
            )
            results = await self._client.query_points(
                collection_name=self._collection_name,
                query_filter=bm25_filter,
                limit=top_k,
            )
            return [self._point_to_dict(point) for point in results.points]
        except UnexpectedResponse as exc:
            logger.error(
                "Qdrant BM25 검색 에러: collection=%s status=%s",
                self._collection_name,
                getattr(exc, "status_code", "unknown"),
            )
            raise VectorStoreException(
                msg=f"Qdrant BM25 검색 에러: {exc}"
            ) from exc
        except httpx.ConnectError as exc:
            logger.error(
                "Qdrant BM25 연결 실패: collection=%s",
                self._collection_name,
            )
            raise VectorStoreException(
                msg=f"Qdrant BM25 연결 실패: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            logger.error(
                "Qdrant BM25 요청 타임아웃: collection=%s",
                self._collection_name,
            )
            raise VectorStoreException(
                msg=f"Qdrant BM25 요청 타임아웃: {exc}"
            ) from exc
        except (KeyError, AttributeError) as exc:
            logger.error(
                "Qdrant BM25 응답 파싱 실패: collection=%s",
                self._collection_name,
            )
            raise VectorStoreException(
                msg=f"Qdrant BM25 응답 파싱 실패: {exc}"
            ) from exc

    async def check_fulltext_index(self) -> bool:
        """text_for_search 필드에 full-text index가 있는지 읽기 전용으로 확인한다.

        앱 startup 단계에서 호출되며 인덱스 부재 시 운영자에게 경고하기 위한 용도.
        Qdrant 쓰기 작업(인덱스 생성)은 수행하지 않는다.

        Returns:
            True: text_for_search 필드에 text 타입 payload index 존재
            False: 인덱스 없음 또는 조회 실패
        """
        try:
            info = await self._client.get_collection(
                collection_name=self._collection_name
            )
            payload_schema = getattr(info, "payload_schema", None) or {}
            field_info = payload_schema.get(self._content_field)
            if field_info is None:
                return False
            data_type = getattr(field_info, "data_type", None)
            type_str = (
                data_type.value if hasattr(data_type, "value") else str(data_type)
            )
            return "text" in type_str.lower()
        except (UnexpectedResponse, httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(
                "Qdrant fulltext index 조회 실패: collection=%s cause=%s",
                self._collection_name, exc,
            )
            return False
        except (KeyError, AttributeError) as exc:
            logger.warning(
                "Qdrant collection_info 파싱 실패: collection=%s cause=%s",
                self._collection_name, exc,
            )
            return False

    async def fetch_chunks_by_parents(
        self,
        parents_by_doc: dict[str, list[int]],
    ) -> list[dict]:
        """주어진 (문서, parent_id 집합)의 모든 청크를 필터 전용으로 회수한다.

        parent-document 확장용. 문서별로 병렬(scroll)로 회수하며 점수는 부여하지
        않는다(랭킹 아님). 반환 dict는 content, metadata, _point_id를 포함한다.
        결과가 없으면 빈 리스트를 반환한다.

        Raises:
            VectorStoreException: Qdrant 연결/조회 실패 시.
        """
        if not parents_by_doc:
            return []
        try:
            batches = await asyncio.gather(
                *[
                    self._scroll_by_parent(doc_id, parent_ids)
                    for doc_id, parent_ids in parents_by_doc.items()
                ]
            )
            return [chunk for batch in batches for chunk in batch]
        except UnexpectedResponse as exc:
            logger.error(
                "Qdrant parent 회수 에러: collection=%s status=%s",
                self._collection_name,
                getattr(exc, "status_code", "unknown"),
            )
            raise VectorStoreException(
                msg=f"Qdrant parent 회수 에러: {exc}"
            ) from exc
        except httpx.ConnectError as exc:
            logger.error(
                "Qdrant parent 회수 연결 실패: collection=%s",
                self._collection_name,
            )
            raise VectorStoreException(
                msg=f"Qdrant parent 회수 연결 실패: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            logger.error(
                "Qdrant parent 회수 타임아웃: collection=%s",
                self._collection_name,
            )
            raise VectorStoreException(
                msg=f"Qdrant parent 회수 타임아웃: {exc}"
            ) from exc
        except (KeyError, AttributeError) as exc:
            logger.error(
                "Qdrant parent 회수 응답 파싱 실패: collection=%s",
                self._collection_name,
            )
            raise VectorStoreException(
                msg=f"Qdrant parent 회수 응답 파싱 실패: {exc}"
            ) from exc

    async def _scroll_by_parent(
        self,
        doc_content_id: str,
        parent_ids: list[int],
    ) -> list[dict]:
        """단일 문서에서 parent_id IN parent_ids 인 활성 청크를 전건 회수한다."""
        query_filter = Filter(
            must=[
                FieldCondition(
                    key=PayloadField.DOC_CONTENT_ID,
                    match=MatchValue(value=doc_content_id),
                ),
                FieldCondition(
                    key=PayloadField.PARENT_ID,
                    match=MatchAny(any=parent_ids),
                ),
                FieldCondition(
                    key=PayloadField.IS_ACTIVE,
                    match=MatchValue(value="Y"),
                ),
            ]
        )
        chunks: list[dict] = []
        offset = None
        while True:
            points, offset = await self._client.scroll(
                collection_name=self._collection_name,
                scroll_filter=query_filter,
                limit=_SCROLL_BATCH,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                chunks.append(
                    {
                        "content": point.payload.get(self._content_field, ""),
                        "metadata": {
                            k: v
                            for k, v in point.payload.items()
                            if k != self._content_field
                        },
                        "_point_id": point.id,
                    }
                )
            if offset is None:
                break
        return chunks
