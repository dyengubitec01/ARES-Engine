"""Qdrant 클라이언트"""
import logging
from typing import List, Dict, Any, Optional, Union
from qdrant_client import QdrantClient as QdrantClientBase
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseVector,
    PointStruct,
    Filter,
    FilterSelector,
    FieldCondition,
    MatchValue,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

logger = logging.getLogger(__name__)

# 하이브리드 컬렉션의 named vector 키
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


class QdrantClient:
    """Qdrant 클라이언트 래퍼

    collection_name과 hybrid 여부를 생성자에서 받아 단일/하이브리드 컬렉션을 모두 다룹니다.
    - hybrid=False: 기존 unnamed 단일 dense 벡터 컬렉션 (호환성 유지)
    - hybrid=True : named dense + sparse 벡터 컬렉션
    """

    UPSERT_BATCH_SIZE = 500  # 한 번에 업서트할 최대 포인트 수

    def __init__(
        self,
        collection_name: Optional[str] = None,
        hybrid: bool = False,
    ):
        self.client = QdrantClientBase(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=60,
        )
        self.collection_name = collection_name or settings.qdrant_collection
        self.hybrid = hybrid
        self._ensure_collection()

    def _ensure_collection(self):
        """컬렉션이 존재하는지 확인하고 없으면 생성"""
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if self.collection_name in collection_names:
            return

        if self.hybrid:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    DENSE_VECTOR_NAME: VectorParams(
                        size=settings.qdrant_vector_size,
                        distance=Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    SPARSE_VECTOR_NAME: SparseVectorParams(),
                },
            )
            logger.info(
                "Qdrant 하이브리드 컬렉션 생성: %s (dense=%d, sparse)",
                self.collection_name, settings.qdrant_vector_size,
            )
        else:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=settings.qdrant_vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Qdrant 컬렉션 생성: {self.collection_name}")
    
    def upsert_points(
        self,
        points: List[PointStruct]
    ) -> bool:
        """포인트 일괄 업서트 (자동 배치 분할)"""
        total = len(points)
        if total == 0:
            return True

        for start in range(0, total, self.UPSERT_BATCH_SIZE):
            batch = points[start:start + self.UPSERT_BATCH_SIZE]
            self._upsert_batch(batch)
            logger.info(
                "Qdrant 업서트 진행: %d/%d 포인트 완료",
                min(start + self.UPSERT_BATCH_SIZE, total), total,
            )
        return True

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _upsert_batch(self, batch: List[PointStruct]):
        """단일 배치 업서트 (재시도 포함)"""
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
        except Exception as e:
            logger.error(f"Qdrant 업서트 실패 ({len(batch)}개 포인트): {e}")
            raise
    
    def create_point(
        self,
        point_id: str,
        vector: List[float],
        payload: Dict[str, Any]
    ) -> PointStruct:
        """포인트 생성 (단일 dense 벡터)"""
        return PointStruct(
            id=point_id,
            vector=vector,
            payload=payload
        )

    def create_hybrid_point(
        self,
        point_id: str,
        dense_vector: List[float],
        sparse_indices: List[int],
        sparse_values: List[float],
        payload: Dict[str, Any],
    ) -> PointStruct:
        """포인트 생성 (하이브리드: dense + sparse named vectors)"""
        return PointStruct(
            id=point_id,
            vector={
                DENSE_VECTOR_NAME: dense_vector,
                SPARSE_VECTOR_NAME: SparseVector(
                    indices=sparse_indices,
                    values=sparse_values,
                ),
            },
            payload=payload,
        )
    
    def delete_by_doc_content_id(self, doc_content_id: str) -> bool:
        """특정 문서의 모든 포인트 삭제"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="doc_content_id",
                                match=MatchValue(value=doc_content_id),
                            )
                        ]
                    )
                ),
            )
            logger.info(
                "Qdrant 포인트 삭제 완료: collection=%s, doc_content_id=%s",
                self.collection_name, doc_content_id,
            )
            return True
        except Exception as e:
            logger.error("Qdrant 포인트 삭제 실패: doc_content_id=%s, error=%s", doc_content_id, e)
            raise

    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
        vector_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """벡터 검색 (named vector 사용 시 vector_name 지정)"""
        try:
            kwargs = {
                "collection_name": self.collection_name,
                "query": query_vector,
                "limit": limit,
                "score_threshold": score_threshold,
                "with_payload": True,
            }
            if vector_name:
                kwargs["using"] = vector_name
            response = self.client.query_points(**kwargs)
            points = getattr(response, "points", [])
            hits: List[Dict[str, Any]] = []
            for point in points:
                hits.append(
                    {
                        "id": getattr(point, "id", None),
                        "score": getattr(point, "score", None),
                        "payload": getattr(point, "payload", None),
                    }
                )
            return hits
        except Exception as e:
            logger.error(f"Qdrant 검색 실패: {e}")
            raise






