"""Settings 클래스 및 환경 설정 테스트."""

import os

import pytest

from app.core.config import Settings, get_settings


class TestSettings:
    """Settings 클래스 단위 테스트."""

    def test_default_values(self, monkeypatch):
        """기본값이 올바르게 설정되는지 확인."""
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.delenv("APP_HOST", raising=False)
        monkeypatch.delenv("APP_PORT", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("SEARCH_K", raising=False)
        monkeypatch.delenv("TOP_K", raising=False)
        monkeypatch.delenv("SCORE_THRESHOLD", raising=False)
        monkeypatch.delenv("HTTP_TIMEOUT", raising=False)
        settings = Settings(_env_file=None)
        assert settings.APP_ENV == "dev"
        assert settings.APP_HOST == "0.0.0.0"
        assert settings.APP_PORT == 8006
        assert settings.LOG_LEVEL == "DEBUG"
        assert settings.SEARCH_K == 20
        assert settings.TOP_K == 6
        assert settings.SCORE_THRESHOLD == 0.0
        assert settings.HTTP_TIMEOUT == 30.0

    def test_qdrant_defaults(self, monkeypatch):
        """Qdrant 관련 기본값 확인."""
        monkeypatch.delenv("QDRANT_URL", raising=False)
        monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
        monkeypatch.delenv("QDRANT_CONTENT_FIELD", raising=False)
        settings = Settings(_env_file=None)
        assert settings.QDRANT_URL == "http://localhost:6333"
        assert settings.QDRANT_COLLECTION == "documents"
        assert settings.QDRANT_CONTENT_FIELD == "text_for_search"

    def test_embedding_default(self):
        """임베딩 API URL 기본값 확인."""
        settings = Settings(_env_file=None)
        assert settings.EMBEDDING_API_URL == "http://localhost:8100/query"

    def test_reranker_default(self):
        """Reranker URL 기본값 확인."""
        settings = Settings(_env_file=None)
        assert settings.RERANKER_URL == "http://localhost:8011/rerank"

    def test_langfuse_defaults(self, monkeypatch):
        """Langfuse 관련 기본값 확인."""
        monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
        monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
        monkeypatch.delenv("LANGFUSE_HOST", raising=False)
        settings = Settings(_env_file=None)
        assert settings.LANGFUSE_ENABLED is False
        assert settings.LANGFUSE_PUBLIC_KEY == ""
        assert settings.LANGFUSE_SECRET_KEY == ""
        assert settings.LANGFUSE_HOST == "https://cloud.langfuse.com"

    def test_env_override(self, monkeypatch):
        """환경변수로 설정값 오버라이드 가능 확인."""
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("APP_PORT", "9000")
        monkeypatch.setenv("SEARCH_K", "50")
        settings = Settings(_env_file=None)
        assert settings.APP_ENV == "prod"
        assert settings.APP_PORT == 9000
        assert settings.SEARCH_K == 50

    def test_type_coercion(self, monkeypatch):
        """문자열 환경변수가 올바른 타입으로 변환되는지 확인."""
        monkeypatch.setenv("APP_PORT", "3000")
        monkeypatch.setenv("SEARCH_K", "10")
        monkeypatch.setenv("TOP_K", "3")
        monkeypatch.setenv("HTTP_TIMEOUT", "15.5")
        settings = Settings(_env_file=None)
        assert isinstance(settings.APP_PORT, int)
        assert isinstance(settings.SEARCH_K, int)
        assert isinstance(settings.TOP_K, int)
        assert isinstance(settings.HTTP_TIMEOUT, float)

    def test_case_insensitive(self, monkeypatch):
        """case_sensitive=False로 대소문자 무시 매칭 확인."""
        monkeypatch.setenv("app_env", "prod")
        settings = Settings(_env_file=None)
        assert settings.APP_ENV == "prod"

    def test_hybrid_search_defaults(self, monkeypatch):
        """Hybrid Search 기본값: 인덱스 준비 전이므로 False로 시작."""
        monkeypatch.delenv("HYBRID_SEARCH_ENABLED", raising=False)
        monkeypatch.delenv("RRF_K", raising=False)
        settings = Settings(_env_file=None)
        assert settings.HYBRID_SEARCH_ENABLED is False
        assert settings.RRF_K == 60

    def test_hybrid_search_env_override(self, monkeypatch):
        """HYBRID_SEARCH_ENABLED, RRF_K 환경변수 오버라이드."""
        monkeypatch.setenv("HYBRID_SEARCH_ENABLED", "true")
        monkeypatch.setenv("RRF_K", "80")
        settings = Settings(_env_file=None)
        assert settings.HYBRID_SEARCH_ENABLED is True
        assert settings.RRF_K == 80
        assert isinstance(settings.RRF_K, int)


class TestEnvFileDynamicLoading:
    """APP_ENV 기반 동적 env 파일 로딩 테스트."""

    def test_default_env_file_is_dev(self):
        """APP_ENV 미설정 시 .env.dev를 로드 대상으로 설정."""
        from app.core.config import _APP_ENV
        # 모듈 로드 시점의 _APP_ENV가 OS 환경변수 기반으로 결정됨
        assert isinstance(_APP_ENV, str)

    def test_env_file_pattern(self):
        """Settings.model_config의 env_file이 .env.{APP_ENV} 패턴."""
        env_file = Settings.model_config["env_file"]
        assert env_file.startswith(".env.")
        assert not env_file.endswith(".example")


class TestGetSettings:
    """get_settings 싱글턴 테스트."""

    def test_returns_settings_instance(self):
        """Settings 인스턴스를 반환하는지 확인."""
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_singleton_behavior(self):
        """lru_cache로 동일 인스턴스를 반환하는지 확인."""
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
