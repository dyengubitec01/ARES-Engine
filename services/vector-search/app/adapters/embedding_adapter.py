"""외부 임베딩 API(BGE-M3) 어댑터."""

import logging

import httpx

from app.core.config import Settings
from app.core.exceptions import EmbeddingException
from app.core.interfaces import EmbeddingInterface

logger = logging.getLogger(__name__)


class EmbeddingAdapter(EmbeddingInterface):
    """외부 임베딩 API를 호출하여 텍스트를 벡터로 변환한다.

    BGE-M3 임베딩 서버에 httpx.AsyncClient로 요청을 보낸다.
    """

    def __init__(self, settings: Settings) -> None:
        self._url = settings.EMBEDDING_API_URL
        self._timeout = settings.HTTP_TIMEOUT

    async def embed(self, text: str) -> list[float]:
        """외부 임베딩 API를 호출하여 텍스트를 벡터로 변환한다.

        Args:
            text: 임베딩할 텍스트 문자열.

        Returns:
            임베딩 벡터 (list[float]).

        Raises:
            EmbeddingException: API 호출 실패 시.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._url,
                    json={"query": text},
                )
                response.raise_for_status()
                data = response.json()
                return data["vector"]
        except httpx.TimeoutException as exc:
            logger.error("임베딩 API 타임아웃: url=%s", self._url)
            raise EmbeddingException(
                msg=f"임베딩 API 타임아웃: {exc}"
            ) from exc
        except httpx.ConnectError as exc:
            logger.error("임베딩 API 연결 실패: url=%s", self._url)
            raise EmbeddingException(
                msg=f"임베딩 API 연결 실패: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "임베딩 API HTTP 에러: status=%d url=%s",
                exc.response.status_code,
                self._url,
            )
            raise EmbeddingException(
                msg=f"임베딩 API HTTP 에러: {exc.response.status_code}"
            ) from exc
        except (KeyError, ValueError) as exc:
            logger.error("임베딩 API 응답 파싱 실패: url=%s", self._url)
            raise EmbeddingException(
                msg=f"임베딩 API 응답 파싱 실패: {exc}"
            ) from exc
