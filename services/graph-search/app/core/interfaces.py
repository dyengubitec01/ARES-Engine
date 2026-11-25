"""벡터 스토어, 리랭커, 임베딩 추상 인터페이스."""

from abc import ABC, abstractmethod


class GraphRetrieverInterface(ABC):
    """그래프 기반 청크 회수 어댑터 인터페이스.

    Fail-open 원칙: 실패 시 반드시 빈 리스트를 반환한다.
    """

    @abstractmethod
    async def retrieve(self, query: str, trace_context: dict | None = None) -> list[dict]:
        """query로 그래프 축 후보 청크를 회수한다.

        trace_context: Langfuse child span을 부모 span에 nest하기 위한 컨텍스트
            ({trace_id, parent_span_id}). None이면 계측 없이 동작.

        Returns:
            {chunk_id, content, metadata, score, _source="graph"} 리스트.
            실패·비활성화 시 빈 리스트.
        """


class EmbeddingInterface(ABC):
    """임베딩 어댑터 인터페이스."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """텍스트를 벡터로 변환한다."""
