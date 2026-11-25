"""설정 모듈 테스트."""

import os
from unittest.mock import patch

import pytest

from src.config.loader import _deep_merge, get_config_value, load_config
from src.config.settings import AppEnv, Settings, get_settings


@pytest.fixture(autouse=True)
def clear_config_cache():
    """각 테스트마다 설정 캐시 자동 클리어."""
    load_config.cache_clear()
    get_settings.cache_clear()
    yield
    load_config.cache_clear()
    get_settings.cache_clear()


class TestSettings:
    """Settings 클래스 테스트."""

    def test_default_values(self):
        """기본값 테스트."""
        with patch.dict(os.environ, {}, clear=True):
            # _env_file=None → .env 파일 읽기 방지, 순수 기본값만 검증
            settings = Settings(_env_file=None)
            assert settings.app_env == AppEnv.DEVELOPMENT
            assert settings.llm_gateway_url == "http://localhost:4000/v1"
            assert settings.llm_api_key == ""

    def test_env_override(self):
        """환경변수 오버라이드 테스트."""
        env = {
            "APP_ENV": "production",
            "LLM_GATEWAY_URL": "http://prod:4000/v1",
            "LLM_API_KEY": "test-key",
        }
        with patch.dict(os.environ, env, clear=True):
            settings = Settings()
            assert settings.app_env == AppEnv.PRODUCTION
            assert settings.llm_gateway_url == "http://prod:4000/v1"
            assert settings.llm_api_key == "test-key"

    def test_is_production(self):
        """운영 환경 판별 테스트."""
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=True):
            settings = Settings()
            assert settings.is_production is True
            assert settings.is_development is False

    def test_is_development(self):
        """개발 환경 판별 테스트."""
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=True):
            settings = Settings()
            assert settings.is_development is True
            assert settings.is_production is False


class TestDeepMerge:
    """_deep_merge 함수 테스트."""

    def test_simple_merge(self):
        """단순 병합 테스트."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        """중첩 병합 테스트."""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 20, "z": 30}}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3}

    def test_base_unchanged(self):
        """원본 딕셔너리 불변 테스트."""
        base = {"a": 1}
        override = {"a": 2}
        _deep_merge(base, override)
        assert base == {"a": 1}


class TestLoadConfig:
    """load_config 함수 테스트."""

    def test_load_config_returns_dict(self):
        """설정 로드 결과가 딕셔너리인지 테스트."""
        config = load_config()
        assert isinstance(config, dict)
        assert "app" in config

    def test_app_name_exists(self):
        """앱 이름 설정 존재 테스트."""
        config = load_config()
        assert config["app"]["name"] == "TOL"


class TestGetConfigValue:
    """get_config_value 함수 테스트."""

    def test_dot_notation(self):
        """점 표기법 테스트."""
        value = get_config_value("app.name")
        assert value == "TOL"

    def test_nested_key(self):
        """중첩 키 테스트."""
        value = get_config_value("llm.default_timeout")
        assert isinstance(value, int)

    def test_missing_key_default(self):
        """없는 키 기본값 테스트."""
        value = get_config_value("nonexistent.key", default="fallback")
        assert value == "fallback"

    def test_missing_key_none(self):
        """없는 키 None 반환 테스트."""
        value = get_config_value("nonexistent.key")
        assert value is None


class TestEnvironmentOverride:
    """환경별 설정 오버라이드 테스트."""

    def test_development_override(self):
        """개발 환경 설정 오버라이드 테스트."""
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=True):
            timeout = get_config_value("llm.default_timeout")
            assert timeout == 60  # config.development.yaml

            level = get_config_value("logging.level")
            assert level == "DEBUG"

    def test_production_override(self):
        """운영 환경 설정 오버라이드 테스트."""
        with patch.dict(os.environ, {"APP_ENV": "production"}, clear=True):
            timeout = get_config_value("llm.default_timeout")
            assert timeout == 30  # config.production.yaml

            level = get_config_value("logging.level")
            assert level == "WARNING"

    def test_base_config_preserved(self):
        """기본 설정값 유지 테스트."""
        with patch.dict(os.environ, {"APP_ENV": "development"}, clear=True):
            # 오버라이드 되지 않은 값은 기본값 유지
            app_name = get_config_value("app.name")
            assert app_name == "TOL"

            scopes = get_config_value("scoping.allowed_scopes")
            assert "agent" in scopes
            assert "backend" in scopes
