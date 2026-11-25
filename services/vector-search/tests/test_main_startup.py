"""앱 startup 훅 — fulltext index 검증 및 Hybrid Search 자동 비활성화 테스트."""

import logging
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.core.interfaces import VectorStoreInterface
from app.main import disable_hybrid_if_fulltext_index_missing


class TestDisableHybridIfFulltextIndexMissing:
    """disable_hybrid_if_fulltext_index_missing 동작 검증."""

    def _settings(self, enabled: bool) -> Settings:
        return Settings(
            _env_file=None,
            HYBRID_SEARCH_ENABLED=enabled,
            QDRANT_COLLECTION="test-collection",
        )

    async def test_noop_when_hybrid_disabled(self):
        """HYBRID_SEARCH_ENABLED=False면 check를 호출하지 않는다."""
        settings = self._settings(enabled=False)
        store = AsyncMock(spec=VectorStoreInterface)
        await disable_hybrid_if_fulltext_index_missing(settings, store)
        store.check_fulltext_index.assert_not_called()
        assert settings.HYBRID_SEARCH_ENABLED is False

    async def test_keeps_enabled_when_index_exists(self):
        """인덱스가 존재하면 플래그를 그대로 유지한다."""
        settings = self._settings(enabled=True)
        store = AsyncMock(spec=VectorStoreInterface)
        store.check_fulltext_index.return_value = True

        await disable_hybrid_if_fulltext_index_missing(settings, store)

        store.check_fulltext_index.assert_awaited_once()
        assert settings.HYBRID_SEARCH_ENABLED is True

    async def test_disables_when_index_missing(self, caplog):
        """인덱스가 없으면 HYBRID_SEARCH_ENABLED를 False로 비활성화하고 ERROR 로그 기록."""
        settings = self._settings(enabled=True)
        store = AsyncMock(spec=VectorStoreInterface)
        store.check_fulltext_index.return_value = False

        with caplog.at_level(logging.ERROR):
            await disable_hybrid_if_fulltext_index_missing(settings, store)

        assert settings.HYBRID_SEARCH_ENABLED is False
        assert "Hybrid Search 비활성화" in caplog.text
        assert "test-collection" in caplog.text

    async def test_disables_when_check_raises(self, caplog):
        """check_fulltext_index가 예외를 던지면 자동 비활성화 + WARN 로그."""
        settings = self._settings(enabled=True)
        store = AsyncMock(spec=VectorStoreInterface)
        store.check_fulltext_index.side_effect = RuntimeError("qdrant unreachable")

        with caplog.at_level(logging.WARNING):
            await disable_hybrid_if_fulltext_index_missing(settings, store)

        assert settings.HYBRID_SEARCH_ENABLED is False
        assert "Fulltext index 검증 중 오류" in caplog.text

    async def test_no_exception_leaks_on_failure(self):
        """startup 검증은 어떤 경우에도 앱 기동을 막지 않는다(예외 전파 없음)."""
        settings = self._settings(enabled=True)
        store = AsyncMock(spec=VectorStoreInterface)
        store.check_fulltext_index.side_effect = Exception("catastrophic")

        # 예외가 바깥으로 나오면 앱 기동 실패로 이어지므로 반드시 삼켜야 한다
        await disable_hybrid_if_fulltext_index_missing(settings, store)
        assert settings.HYBRID_SEARCH_ENABLED is False
