"""벡터 스토어, 리랭커, 임베딩 추상 인터페이스."""

from abc import ABC, abstractmethod


class VectorStoreInterface(ABC):
    """벡터 검색 어댑터 인터페이스."""

    @abstractmethod
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
            _point_id는 RRF 합산 시 중복 판별 키로 사용된다.
        """

    @abstractmethod
    async def text_search(
        self,
        query_text: str,
        top_k: int,
        user_depts: list[str],
        excluded_docs: list[str] | None = None,
    ) -> list[dict]:
        """BM25 기반 full-text 검색을 수행한다.

        Args:
            query_text: 검색 쿼리 문자열.
            top_k: 반환할 최대 결과 수.
            user_depts: 부서 UUID 리스트. 검색 필터에는 사용하지 않는다(부서 필터 개방) — 로깅·모니터링 목적으로만 전달된다.
            excluded_docs: 제외할 doc_content_id 리스트.

        Returns:
            검색 결과 리스트. 각 항목은 content, metadata, score, _point_id를 포함한다.
            score는 Qdrant 내부 BM25 점수로 dense의 cosine similarity와 스케일이 다르다.
        """

    @abstractmethod
    async def check_fulltext_index(self) -> bool:
        """text_for_search 필드에 full-text index가 존재하는지 확인한다.

        Qdrant collection_info를 읽어 payload index 정보를 조회한다.
        쓰기 작업은 수행하지 않는다.

        Returns:
            True: text_for_search 필드에 text index 존재
            False: 인덱스 없음 또는 Qdrant 연결 실패
        """

    @abstractmethod
    async def fetch_chunks_by_parents(
        self,
        parents_by_doc: dict[str, list[int]],
    ) -> list[dict]:
        """주어진 (문서, parent_id 집합)에 속한 모든 청크를 회수한다.

        parent-document 확장에서 사용한다. 점수(랭킹) 없이 필터 전용으로 회수하며,
        반환 dict는 content, metadata, _point_id를 포함한다.

        Args:
            parents_by_doc: doc_content_id → 회수할 parent_id 리스트.

        Returns:
            매칭된 모든 청크의 dict 리스트. 입력이 비면 빈 리스트.
        """


class EmbeddingInterface(ABC):
    """임베딩 어댑터 인터페이스."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """텍스트를 벡터로 변환한다.

        Args:
            text: 임베딩할 텍스트 문자열.

        Returns:
            임베딩 벡터 (list[float]).
        """


class RerankerInterface(ABC):
    """리랭커 어댑터 인터페이스."""

    @abstractmethod
    async def rerank(
        self, query: str, texts: list[str], top_k: int
    ) -> list[dict]:
        """텍스트 리랭킹을 수행한다.

        Args:
            query: 원본 쿼리 문자열.
            texts: 리랭킹할 후보 텍스트 리스트.
            top_k: 반환할 최대 결과 수.

        Returns:
            리랭킹 결과 리스트. 각 항목은 index, score, text를 포함한다.
        """
