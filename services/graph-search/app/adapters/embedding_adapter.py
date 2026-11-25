"""BGE-M3 임베딩 어댑터 (OpenAI-compatible).

엔티티 링킹 cosine fallback에서 surface 임베딩용으로만 호출된다.
"""

import logging

import httpx

from app.core.config import Settings
from app.core.interfaces import EmbeddingInterface

logger = logging.getLogger(__name__)


class EmbeddingAdapter(EmbeddingInterface):
    def __init__(self, settings: Settings) -> None:
        self._url = settings.EMBEDDING_URL
        self._api_key = settings.EMBEDDING_API_KEY
        self._model = settings.EMBEDDING_MODEL
        self._timeout = settings.HTTP_TIMEOUT

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._url,
                json={"model": self._model, "input": [text]},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            data = response.json()
        # index 순 정렬 (실질적으로 하나뿐)
        items = sorted(data["data"], key=lambda x: x["index"])
        return items[0]["embedding"]
