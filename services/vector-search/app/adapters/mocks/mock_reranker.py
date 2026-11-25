"""Mock 리랭커 어댑터 (테스트/개발용)."""

from app.core.interfaces import RerankerInterface


class MockReranker(RerankerInterface):
    """테스트용 Mock 리랭커.

    실제 리랭커 API 호출 없이 입력 텍스트에 점수를 부여하여 반환한다.
    """

    async def rerank(
        self, query: str, texts: list[str], top_k: int
    ) -> list[dict]:
        """입력 텍스트를 점수와 함께 정렬된 형태로 반환한다."""
        scored = [
            {
                "index": i,
                "score": round(0.99 - (i * 0.03), 2),
                "text": text,
            }
            for i, text in enumerate(texts)
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
