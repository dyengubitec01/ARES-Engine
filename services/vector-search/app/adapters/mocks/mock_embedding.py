"""Mock 임베딩 어댑터 (테스트/개발용)."""

from app.core.interfaces import EmbeddingInterface


class MockEmbeddingAdapter(EmbeddingInterface):
    """테스트용 Mock 임베딩 어댑터.

    실제 임베딩 API 호출 없이 고정 차원의 더미 벡터를 반환한다.
    """

    _DIMENSION = 1024

    async def embed(self, text: str) -> list[float]:
        """고정 차원(1024)의 더미 벡터를 반환한다."""
        return [0.0] * self._DIMENSION
