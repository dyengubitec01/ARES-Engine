"""모델 설정 모듈 테스트."""

from pathlib import Path

import pytest
import yaml

from src.config.models import (
    ModelRole,
    ModelsConfig,
    get_fallback_chain,
    get_model_for_role,
    load_models_config,
)

# models.yaml 원본에서 기대값 로드 — 하드코딩 방지
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
with (_PROJECT_ROOT / "config" / "models.yaml").open(encoding="utf-8") as _f:
    _RAW_MODELS = yaml.safe_load(_f)

_EXPECTED_PRIMARY = _RAW_MODELS["roles"]["primary"]["model"]
_EXPECTED_FAST = _RAW_MODELS["roles"]["fast"]["model"]
_EXPECTED_REASONING = _RAW_MODELS["roles"]["reasoning"]["model"]


@pytest.fixture(autouse=True)
def clear_models_cache():
    """각 테스트마다 모델 설정 캐시 자동 클리어."""
    load_models_config.cache_clear()
    yield
    load_models_config.cache_clear()


class TestLoadModelsConfig:
    """load_models_config 함수 테스트."""

    def test_returns_models_config(self):
        """ModelsConfig 인스턴스 반환 테스트."""
        config = load_models_config()
        assert isinstance(config, ModelsConfig)

    def test_has_roles(self):
        """역할 존재 테스트."""
        config = load_models_config()
        assert len(config.roles) > 0

    def test_has_primary_role(self):
        """primary 역할 존재 테스트."""
        config = load_models_config()
        assert "primary" in config.roles

    def test_has_fast_role(self):
        """fast 역할 존재 테스트."""
        config = load_models_config()
        assert "fast" in config.roles

    def test_has_reasoning_role(self):
        """reasoning 역할 존재 테스트."""
        config = load_models_config()
        assert "reasoning" in config.roles

    def test_default_role(self):
        """기본 역할 테스트."""
        config = load_models_config()
        assert config.default_role == "primary"

    def test_fallback_message(self):
        """fallback 메시지 존재 테스트."""
        config = load_models_config()
        assert config.fallback_message
        assert len(config.fallback_message) > 0


class TestModelRole:
    """ModelRole 데이터 클래스 테스트."""

    def test_primary_role_info(self):
        """primary 역할 정보 테스트."""
        config = load_models_config()
        primary = config.get_role("primary")

        assert primary is not None
        assert isinstance(primary, ModelRole)
        assert primary.role == "primary"
        assert primary.model == _EXPECTED_PRIMARY
        assert primary.fallback_role == "fast"

    def test_fast_role_info(self):
        """fast 역할 정보 테스트."""
        config = load_models_config()
        fast = config.get_role("fast")

        assert fast is not None
        assert fast.model == _EXPECTED_FAST
        assert fast.fallback_role is None

    def test_reasoning_role_info(self):
        """reasoning 역할 정보 테스트."""
        config = load_models_config()
        reasoning = config.get_role("reasoning")

        assert reasoning is not None
        assert reasoning.model == _EXPECTED_REASONING
        assert reasoning.fallback_role == "primary"


class TestGetModel:
    """get_model 메서드 테스트."""

    def test_get_model_primary(self):
        """primary 모델 조회 테스트."""
        config = load_models_config()
        assert config.get_model("primary") == _EXPECTED_PRIMARY

    def test_get_model_fast(self):
        """fast 모델 조회 테스트."""
        config = load_models_config()
        assert config.get_model("fast") == _EXPECTED_FAST

    def test_get_model_nonexistent(self):
        """없는 역할 조회 테스트."""
        config = load_models_config()
        assert config.get_model("nonexistent") is None


class TestGetFallbackChain:
    """fallback 체인 테스트."""

    def test_primary_fallback_chain(self):
        """primary fallback 체인 테스트."""
        config = load_models_config()
        chain = config.get_fallback_chain("primary")

        assert chain == ["primary", "fast"]

    def test_fast_fallback_chain(self):
        """fast fallback 체인 테스트 (종단점)."""
        config = load_models_config()
        chain = config.get_fallback_chain("fast")

        assert chain == ["fast"]

    def test_reasoning_fallback_chain(self):
        """reasoning fallback 체인 테스트."""
        config = load_models_config()
        chain = config.get_fallback_chain("reasoning")

        assert chain == ["reasoning", "primary", "fast"]

    def test_nonexistent_fallback_chain(self):
        """없는 역할 fallback 체인 테스트."""
        config = load_models_config()
        chain = config.get_fallback_chain("nonexistent")

        assert chain == []


class TestHelperFunctions:
    """헬퍼 함수 테스트."""

    def test_get_model_for_role_primary(self):
        """get_model_for_role primary 테스트."""
        assert get_model_for_role("primary") == _EXPECTED_PRIMARY

    def test_get_model_for_role_default(self):
        """get_model_for_role 기본값 테스트."""
        assert get_model_for_role() == _EXPECTED_PRIMARY
        assert get_model_for_role(None) == _EXPECTED_PRIMARY

    def test_get_model_for_role_nonexistent(self):
        """get_model_for_role 없는 역할 테스트."""
        assert get_model_for_role("nonexistent") == ""

    def test_get_fallback_chain_helper(self):
        """get_fallback_chain 헬퍼 함수 테스트."""
        assert get_fallback_chain("primary") == ["primary", "fast"]

    def test_get_fallback_chain_default(self):
        """get_fallback_chain 기본값 테스트."""
        assert get_fallback_chain() == ["primary", "fast"]
        assert get_fallback_chain(None) == ["primary", "fast"]
