"""Tests for LangFuse Prompt Management (Story 3.4)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.core.prompt_manager import PromptConfig, PromptManager

# ============================================================================
# PromptConfig Tests
# ============================================================================


class TestPromptConfig:
    """config/prompts.yaml 로딩 및 메타데이터 접근 테스트."""

    @pytest.fixture()
    def config_file(self, tmp_path: Path) -> Path:
        path = tmp_path / "prompts.yaml"
        path.write_text(
            """
prompts:
  rewriter:
    variables: [history, query]
    type: chat
  synthesizer:
    variables: [history, context, query]
    type: chat
""",
            encoding="utf-8",
        )
        return path

    def test_load_config(self, config_file: Path) -> None:
        config = PromptConfig(config_file)
        assert "rewriter" in config.prompt_names
        assert "synthesizer" in config.prompt_names

    def test_get_variables(self, config_file: Path) -> None:
        config = PromptConfig(config_file)
        assert config.get_variables("rewriter") == {"history", "query"}
        assert config.get_variables("synthesizer") == {"history", "context", "query"}

    def test_get_type(self, config_file: Path) -> None:
        config = PromptConfig(config_file)
        assert config.get_type("rewriter") == "chat"

    def test_unknown_prompt_raises(self, config_file: Path) -> None:
        config = PromptConfig(config_file)
        with pytest.raises(KeyError, match="Unknown prompt"):
            config.get_variables("nonexistent")

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            PromptConfig(tmp_path / "missing.yaml")


# ============================================================================
# PromptManager Tests
# ============================================================================


@pytest.fixture()
def prompt_config(tmp_path: Path) -> PromptConfig:
    path = tmp_path / "prompts.yaml"
    path.write_text(
        """
prompts:
  rewriter:
    variables: [history, query]
    type: chat
  synthesizer:
    variables: [history, context, query]
    type: chat
""",
        encoding="utf-8",
    )
    return PromptConfig(path)


class TestPromptManagerFallbackChain:
    """Fallback 체인 동작 검증 (AC 3.4.2)."""

    def test_fallback_to_hardcoded_when_disabled(
        self, prompt_config: PromptConfig
    ) -> None:
        """LANGFUSE_PROMPT_ENABLED=false → 코드 하드코딩 fallback 사용 (AC 3.4.4)."""
        manager = PromptManager(config=prompt_config)

        hardcoded = [
            ("system", "You are a rewriter. {history}"),
            ("user", "{query}"),
        ]

        with patch(
            "app.core.prompt_manager.settings"
        ) as mock_settings:
            mock_settings.langfuse_prompt_enabled = False
            prompt = manager.get_prompt("rewriter", fallback_messages=hardcoded)

        assert prompt is not None
        # ChatPromptTemplate이 올바른 변수를 가지고 있는지
        assert "history" in prompt.input_variables
        assert "query" in prompt.input_variables

    def test_fallback_to_json_when_langfuse_fails(
        self, prompt_config: PromptConfig, tmp_path: Path
    ) -> None:
        """LangFuse 실패 → fallback JSON 사용 (AC 3.4.2)."""
        manager = PromptManager(config=prompt_config)

        # fallback JSON 생성
        fallback_dir = tmp_path / "fallback"
        fallback_dir.mkdir()
        fallback_json = fallback_dir / "rewriter.json"
        fallback_json.write_text(
            json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": "JSON fallback {history}"},
                        {"role": "user", "content": "{query}"},
                    ]
                }
            ),
            encoding="utf-8",
        )

        with (
            patch("app.core.prompt_manager.settings") as mock_settings,
            patch("app.core.prompt_manager.FALLBACK_DIR", fallback_dir),
        ):
            mock_settings.langfuse_prompt_enabled = True
            mock_settings.APP_ENV = "dev"
            mock_settings.LANGFUSE_PROMPT_CACHE_TTL = 300

            # LangFuse fetch 실패 시뮬레이션
            mock_langfuse = MagicMock()
            mock_langfuse.get_prompt.side_effect = Exception("Connection failed")
            manager._langfuse_client = mock_langfuse

            prompt = manager.get_prompt("rewriter")

        assert prompt is not None
        assert "history" in prompt.input_variables

    def test_fallback_to_hardcoded_when_json_missing(
        self, prompt_config: PromptConfig, tmp_path: Path
    ) -> None:
        """LangFuse 실패 + JSON 없음 → 코드 하드코딩 (AC 3.4.2)."""
        manager = PromptManager(config=prompt_config)

        hardcoded = [
            ("system", "Hardcoded rewriter {history}"),
            ("user", "{query}"),
        ]

        with (
            patch("app.core.prompt_manager.settings") as mock_settings,
            patch("app.core.prompt_manager.FALLBACK_DIR", tmp_path / "empty"),
        ):
            mock_settings.langfuse_prompt_enabled = True
            mock_settings.APP_ENV = "dev"
            mock_settings.LANGFUSE_PROMPT_CACHE_TTL = 300

            mock_langfuse = MagicMock()
            mock_langfuse.get_prompt.side_effect = Exception("Connection failed")
            manager._langfuse_client = mock_langfuse

            prompt = manager.get_prompt("rewriter", fallback_messages=hardcoded)

        assert prompt is not None
        assert "history" in prompt.input_variables

    def test_no_fallback_raises_runtime_error(
        self, prompt_config: PromptConfig, tmp_path: Path
    ) -> None:
        """모든 fallback 소진 시 RuntimeError."""
        manager = PromptManager(config=prompt_config)

        with (
            patch("app.core.prompt_manager.settings") as mock_settings,
            patch("app.core.prompt_manager.FALLBACK_DIR", tmp_path / "empty"),
        ):
            mock_settings.langfuse_prompt_enabled = True
            mock_settings.APP_ENV = "dev"
            mock_settings.LANGFUSE_PROMPT_CACHE_TTL = 300

            mock_langfuse = MagicMock()
            mock_langfuse.get_prompt.side_effect = Exception("Connection failed")
            manager._langfuse_client = mock_langfuse

            with pytest.raises(RuntimeError, match="No prompt available"):
                manager.get_prompt("rewriter")


class TestPromptManagerLangFuse:
    """LangFuse fetch 성공 경로 검증 (AC 3.4.1)."""

    def test_fetch_from_langfuse(self, prompt_config: PromptConfig) -> None:
        """LangFuse에서 프롬프트 정상 조회."""
        manager = PromptManager(config=prompt_config)

        mock_lf_prompt = MagicMock()
        mock_lf_prompt.is_fallback = False
        mock_lf_prompt.get_langchain_prompt.return_value = [
            ("system", "LangFuse rewriter {history}"),
            ("user", "{query}"),
        ]

        mock_langfuse = MagicMock()
        mock_langfuse.get_prompt.return_value = mock_lf_prompt
        manager._langfuse_client = mock_langfuse

        with patch("app.core.prompt_manager.settings") as mock_settings:
            mock_settings.langfuse_prompt_enabled = True
            mock_settings.APP_ENV = "prod"
            mock_settings.LANGFUSE_PROMPT_CACHE_TTL = 300

            prompt = manager.get_prompt("rewriter")

        assert prompt is not None
        mock_langfuse.get_prompt.assert_called_once_with(
            "rewriter",
            label="production",
            type="chat",
            cache_ttl_seconds=300,
        )

    def test_label_always_production(self, prompt_config: PromptConfig) -> None:
        """환경 분리는 LangFuse 프로젝트(API 키)로 처리, 라벨은 항상 production."""
        manager = PromptManager(config=prompt_config)

        mock_lf_prompt = MagicMock()
        mock_lf_prompt.is_fallback = False
        mock_lf_prompt.get_langchain_prompt.return_value = [
            ("system", "test {history}"),
            ("user", "{query}"),
        ]

        mock_langfuse = MagicMock()
        mock_langfuse.get_prompt.return_value = mock_lf_prompt
        manager._langfuse_client = mock_langfuse

        # APP_ENV=dev여도 라벨은 production
        with patch("app.core.prompt_manager.settings") as mock_settings:
            mock_settings.langfuse_prompt_enabled = True
            mock_settings.APP_ENV = "dev"
            mock_settings.LANGFUSE_PROMPT_CACHE_TTL = 300

            manager.get_prompt("rewriter")

        mock_langfuse.get_prompt.assert_called_once_with(
            "rewriter",
            label="production",
            type="chat",
            cache_ttl_seconds=300,
        )


class TestPromptManagerDisabled:
    """비활성화 모드 검증 (AC 3.4.4)."""

    def test_disabled_skips_langfuse_call(
        self, prompt_config: PromptConfig
    ) -> None:
        """LANGFUSE_PROMPT_ENABLED=false → LangFuse API 호출 안 함."""
        manager = PromptManager(config=prompt_config)

        hardcoded = [
            ("system", "Hardcoded {history}"),
            ("user", "{query}"),
        ]

        mock_langfuse = MagicMock()
        manager._langfuse_client = mock_langfuse

        with patch("app.core.prompt_manager.settings") as mock_settings:
            mock_settings.langfuse_prompt_enabled = False

            prompt = manager.get_prompt("rewriter", fallback_messages=hardcoded)

        mock_langfuse.get_prompt.assert_not_called()
        assert prompt is not None


class TestPromptManagerValidation:
    """변수 검증 테스트 (AC 3.4.6)."""

    def test_validate_matching_variables(self, prompt_config: PromptConfig) -> None:
        manager = PromptManager(config=prompt_config)
        # 일치 → 예외 없음
        manager.validate_variables("rewriter", {"history", "query"})

    def test_validate_mismatched_variables_raises(
        self, prompt_config: PromptConfig
    ) -> None:
        manager = PromptManager(config=prompt_config)
        with pytest.raises(ValueError, match="Variable mismatch"):
            manager.validate_variables("rewriter", {"history", "question"})


class TestPromptManagerPrefetch:
    """pre-fetch 동작 검증 (AC 3.4.8)."""

    def test_prefetch_all_calls_langfuse(self, prompt_config: PromptConfig) -> None:
        manager = PromptManager(config=prompt_config)

        mock_langfuse = MagicMock()
        manager._langfuse_client = mock_langfuse

        with patch("app.core.prompt_manager.settings") as mock_settings:
            mock_settings.langfuse_prompt_enabled = True
            mock_settings.APP_ENV = "dev"
            mock_settings.LANGFUSE_PROMPT_CACHE_TTL = 300

            manager.prefetch_all()

        assert mock_langfuse.get_prompt.call_count == 2  # rewriter + synthesizer

    def test_prefetch_skipped_when_disabled(
        self, prompt_config: PromptConfig
    ) -> None:
        manager = PromptManager(config=prompt_config)

        mock_langfuse = MagicMock()
        manager._langfuse_client = mock_langfuse

        with patch("app.core.prompt_manager.settings") as mock_settings:
            mock_settings.langfuse_prompt_enabled = False

            manager.prefetch_all()

        mock_langfuse.get_prompt.assert_not_called()

    def test_prefetch_continues_on_failure(
        self, prompt_config: PromptConfig
    ) -> None:
        """하나가 실패해도 나머지는 계속 시도."""
        manager = PromptManager(config=prompt_config)

        mock_langfuse = MagicMock()
        mock_langfuse.get_prompt.side_effect = [
            Exception("rewriter failed"),
            MagicMock(),  # synthesizer succeeds
        ]
        manager._langfuse_client = mock_langfuse

        with patch("app.core.prompt_manager.settings") as mock_settings:
            mock_settings.langfuse_prompt_enabled = True
            mock_settings.APP_ENV = "dev"
            mock_settings.LANGFUSE_PROMPT_CACHE_TTL = 300

            manager.prefetch_all()  # 예외 발생하지 않음

        assert mock_langfuse.get_prompt.call_count == 2


class TestSettingsPromptConfig:
    """Settings에 추가된 프롬프트 관련 설정 검증."""

    def test_default_prompt_settings(self) -> None:
        s = Settings(_env_file=None)
        assert s.LANGFUSE_PROMPT_ENABLED is True
        assert s.LANGFUSE_PROMPT_CACHE_TTL == 300
        assert s.LANGFUSE_PROMPT_CONFIG_PATH == "config/prompts.yaml"

    def test_prompt_enabled_requires_langfuse(self) -> None:
        """langfuse_prompt_enabled는 LangFuse 키가 있어야 True."""
        s = Settings(
            _env_file=None,
            LANGFUSE_PROMPT_ENABLED=True,
            LANGFUSE_PUBLIC_KEY=None,
            LANGFUSE_SECRET_KEY=None,
        )
        assert s.langfuse_prompt_enabled is False

    def test_prompt_enabled_with_keys(self) -> None:
        s = Settings(
            _env_file=None,
            LANGFUSE_PROMPT_ENABLED=True,
            LANGFUSE_PUBLIC_KEY="pk-test",
            LANGFUSE_SECRET_KEY="sk-test",
        )
        assert s.langfuse_prompt_enabled is True

    def test_prompt_disabled_explicitly(self) -> None:
        s = Settings(
            _env_file=None,
            LANGFUSE_PROMPT_ENABLED=False,
            LANGFUSE_PUBLIC_KEY="pk-test",
            LANGFUSE_SECRET_KEY="sk-test",
        )
        assert s.langfuse_prompt_enabled is False
