r"""GLiNER2 엔티티 추출 API 어댑터."""

import logging
import re

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

_QUERY_BOUNDARY_RE = re.compile(r"[_/\\]+")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_entity_name(name: str) -> str:
    """공백 제거 + casefold. Postgres 저장 규칙과 동일해야 함."""
    return _WHITESPACE_RE.sub("", (name or "").strip()).casefold()


class GLinerAdapter:
    def __init__(self, settings: Settings) -> None:
        self._url = settings.GLINER_URL
        self._api_key = settings.GLINER_API_KEY
        self._timeout = settings.HTTP_TIMEOUT

    async def extract_entities(self, query: str) -> list[dict]:
        """{normalized, surface, type} 리스트. 실패 시 상위에서 흡수."""
        cleaned = _QUERY_BOUNDARY_RE.sub(" ", query)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self._url,
                json={"texts": [cleaned]},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results") or []
        if not results:
            return []
        entities = results[0].get("entities") or []

        out, seen = [], set()
        for e in entities:
            surface = e.get("name") or ""
            if not surface:
                continue
            norm = normalize_entity_name(surface)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            out.append({
                "normalized": norm,
                "surface": surface,
                "type": e.get("type") or "",
            })
        return out
