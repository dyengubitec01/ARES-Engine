"""외부 리랭커 API(bge-reranker-v2-m3) 어댑터."""

import logging

import httpx

from app.core.config import Settings
from app.core.exceptions import RerankerException
from app.core.interfaces import RerankerInterface

logger = logging.getLogger(__name__)


class RerankerAdapter(RerankerInterface):
    """외부 리랭커 API를 호출하여 검색 결과를 정밀 순위화한다.

    bge-reranker-v2-m3 리랭커 서버에 httpx.AsyncClient로 요청을 보낸다.
    """

    def __init__(self, settings: Settings) -> None:
        self._url = settings.RERANKER_URL
        self._timeout = settings.HTTP_TIMEOUT

    async def rerank(
        self, query: str, texts: list[str], top_k: int
    ) -> list[dict]:
        """외부 리랭커 API를 호출하여 텍스트를 정밀 순위화한다.

        Args:
            query: 검색 쿼리 문자열.
            texts: 리랭킹할 텍스트 리스트.
            top_k: 반환할 최대 결과 수.

        Returns:
            리랭킹 결과 (list[dict]). 각 dict에 index, score, text 포함.

        Raises:
            RerankerException: API 호출 실패 시.
        """
        if not texts:
            logger.warning("리랭커 호출 시 빈 텍스트 리스트 전달됨, API 호출 생략")
            return []

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._url,
                    json={"query": query, "texts": texts, "return_text": True},
                )
                response.raise_for_status()
                data = response.json()
                # API 응답 형식 호환: 리스트 직접 반환 or {"value": [...]} 래핑
                results = data if isinstance(data, list) else data["value"]
                return [
                    {"index": item["index"], "score": item["score"], "text": item["text"]}
                    for item in results[:top_k]
                ]
        except httpx.TimeoutException as exc:
            logger.error("리랭커 API 타임아웃: url=%s", self._url)
            raise RerankerException(
                msg=f"리랭커 API 타임아웃: {exc}"
            ) from exc
        except httpx.ConnectError as exc:
            logger.error("리랭커 API 연결 실패: url=%s", self._url)
            raise RerankerException(
                msg=f"리랭커 API 연결 실패: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "리랭커 API HTTP 에러: status=%d url=%s",
                exc.response.status_code,
                self._url,
            )
            raise RerankerException(
                msg=f"리랭커 API HTTP 에러: {exc.response.status_code}"
            ) from exc
        except (KeyError, ValueError, TypeError) as exc:
            logger.error("리랭커 API 응답 파싱 실패: url=%s", self._url)
            raise RerankerException(
                msg=f"리랭커 API 응답 파싱 실패: {exc}"
            ) from exc
