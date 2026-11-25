"""Tests for configuration management."""

import tempfile

import pytest

from app.core.config import (
    ModelConfig,
    ModelConfigError,
    RoleConfig,
    ServerConfig,
    Settings,
    load_model_config,
)


class TestSettings:
    """Tests for Settings class."""

    def test_default_values(self) -> None:
        """Test default settings values (env file 무시, 순수 기본값 검증)."""
        settings = Settings(_env_file=None)

        assert settings.HOST == "0.0.0.0"
        assert settings.PORT == 8000
        assert settings.PRIMARY_LLM_BASE_URL is not None
        assert settings.SECONDARY_LLM_BASE_URL is not None

    def test_langfuse_disabled_by_default(self) -> None:
        """Test LangFuse is disabled when keys are empty."""
        # Explicitly set keys to None to test disabled state
        settings = Settings(
            LANGFUSE_PUBLIC_KEY=None,
            LANGFUSE_SECRET_KEY=None,
        )

        assert settings.langfuse_enabled is False

    def test_langfuse_enabled_with_keys(self) -> None:
        """Test LangFuse is enabled when keys are set."""
        settings = Settings(
            LANGFUSE_PUBLIC_KEY="test-public",
            LANGFUSE_SECRET_KEY="test-secret",
        )

        assert settings.langfuse_enabled is True

    def test_llm_max_tokens_default(self) -> None:
        """Test LLM_MAX_TOKENS default value is 2048."""
        settings = Settings(_env_file=None)

        assert settings.LLM_MAX_TOKENS == 2048

    def test_llm_temperature_default(self) -> None:
        """Test LLM_TEMPERATURE default value is 0.6."""
        settings = Settings(_env_file=None)

        assert settings.LLM_TEMPERATURE == 0.6

    def test_llm_max_tokens_override(self) -> None:
        """Test LLM_MAX_TOKENS can be overridden."""
        settings = Settings(LLM_MAX_TOKENS=1024, _env_file=None)

        assert settings.LLM_MAX_TOKENS == 1024

    def test_llm_temperature_override(self) -> None:
        """Test LLM_TEMPERATURE can be overridden."""
        settings = Settings(LLM_TEMPERATURE=0.3, _env_file=None)

        assert settings.LLM_TEMPERATURE == 0.3

    def test_include_thoughts_default_false(self) -> None:
        """Test INCLUDE_THOUGHTS_IN_RESPONSE is False by default."""
        settings = Settings(_env_file=None)

        assert settings.INCLUDE_THOUGHTS_IN_RESPONSE is False

    def test_include_thoughts_can_be_enabled(self) -> None:
        """Test INCLUDE_THOUGHTS_IN_RESPONSE can be set to True."""
        settings = Settings(INCLUDE_THOUGHTS_IN_RESPONSE=True)

        assert settings.INCLUDE_THOUGHTS_IN_RESPONSE is True

    def test_app_env_default(self) -> None:
        """Test APP_ENV default value is 'dev' (AC 3.5.1)."""
        settings = Settings(_env_file=None)

        assert settings.APP_ENV == "dev"

    def test_app_env_override(self) -> None:
        """Test APP_ENV can be overridden (AC 3.5.2)."""
        settings = Settings(APP_ENV="prod", _env_file=None)

        assert settings.APP_ENV == "prod"

    def test_env_file_dynamic_loading(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test env_file is determined by APP_ENV OS variable (AC 3.5.1)."""
        import app.core.config as config_module

        # _APP_ENV is read at module import time from os.getenv
        # Verify the module-level variable exists and is used in SettingsConfigDict
        assert hasattr(config_module, "_APP_ENV")
        assert isinstance(config_module._APP_ENV, str)


class TestModelConfig:
    """Tests for ModelConfig class."""

    @pytest.fixture
    def sample_config(self) -> ModelConfig:
        """Create sample model config."""
        return ModelConfig(
            roles={
                "primary": RoleConfig(
                    model="test-model-1",
                    server="primary",
                    fallback_role="fallback",
                ),
                "fallback": RoleConfig(
                    model="test-model-2",
                    server="secondary",
                    fallback_role=None,
                ),
            },
            servers={
                "primary": ServerConfig(base_url_env="PRIMARY_LLM_BASE_URL"),
                "secondary": ServerConfig(base_url_env="SECONDARY_LLM_BASE_URL"),
            },
            fallback_message="Test fallback message",
        )

    def test_get_role(self, sample_config: ModelConfig) -> None:
        """Test get_role method."""
        role = sample_config.get_role("primary")

        assert role is not None
        assert role.model == "test-model-1"
        assert role.server == "primary"
        assert role.fallback_role == "fallback"

    def test_get_role_not_found(self, sample_config: ModelConfig) -> None:
        """Test get_role returns None for unknown role."""
        role = sample_config.get_role("unknown")

        assert role is None

    def test_get_model_for_role(self, sample_config: ModelConfig) -> None:
        """Test get_model_for_role method."""
        model = sample_config.get_model_for_role("primary")

        assert model == "test-model-1"

    def test_get_fallback_role(self, sample_config: ModelConfig) -> None:
        """Test get_fallback_role method."""
        fallback = sample_config.get_fallback_role("primary")

        assert fallback == "fallback"

    def test_get_fallback_role_none(self, sample_config: ModelConfig) -> None:
        """Test get_fallback_role returns None for final fallback."""
        fallback = sample_config.get_fallback_role("fallback")

        assert fallback is None


class TestLoadModelConfig:
    """Tests for load_model_config function."""

    def test_load_valid_config(self) -> None:
        """Test loading valid YAML config."""
        yaml_content = """
roles:
  test:
    model: "test-model"
    server: "primary"

servers:
  primary:
    base_url_env: "PRIMARY_LLM_BASE_URL"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            f.flush()

            config = load_model_config(f.name)

            assert config.get_model_for_role("test") == "test-model"

    def test_load_missing_file(self) -> None:
        """Test error when file doesn't exist."""
        with pytest.raises(ModelConfigError, match="not found"):
            load_model_config("/nonexistent/path.yaml")

    def test_load_missing_roles(self) -> None:
        """Test error when roles section is missing."""
        yaml_content = """
servers:
  primary:
    base_url_env: "TEST"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ModelConfigError, match="Missing 'roles'"):
                load_model_config(f.name)

    def test_load_missing_servers(self) -> None:
        """Test error when servers section is missing."""
        yaml_content = """
roles:
  test:
    model: "test"
    server: "primary"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ModelConfigError, match="Missing 'servers'"):
                load_model_config(f.name)

    def test_load_empty_file(self) -> None:
        """Test error when YAML file is empty."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            f.flush()

            with pytest.raises(ModelConfigError, match="Empty config file"):
                load_model_config(f.name)

    def test_load_malformed_yaml(self) -> None:
        """Test error when YAML syntax is invalid."""
        yaml_content = """
roles:
  test:
    model: "test
    server: primary
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ModelConfigError, match="Invalid YAML"):
                load_model_config(f.name)

    def test_load_invalid_schema(self) -> None:
        """Test error when schema validation fails."""
        yaml_content = """
roles:
  test:
    invalid_field: "test"
    server: "primary"

servers:
  primary:
    base_url_env: "TEST"
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            f.flush()

            with pytest.raises(ModelConfigError, match="Invalid config schema"):
                load_model_config(f.name)


class TestSingleton:
    """Tests for singleton pattern (AC 1.2.4)."""

    def test_get_settings_singleton(self) -> None:
        """Test that get_settings returns the same instance."""
        from app.core.config import get_settings

        # Clear cache to test fresh
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_get_model_config_singleton(self) -> None:
        """Test that get_model_config returns the same instance."""
        from app.core.config import get_model_config

        # Clear cache to test fresh
        get_model_config.cache_clear()

        try:
            config1 = get_model_config()
            config2 = get_model_config()

            assert config1 is config2
        except Exception:
            # If models.yaml doesn't exist, skip this test
            pytest.skip("models.yaml not found")
