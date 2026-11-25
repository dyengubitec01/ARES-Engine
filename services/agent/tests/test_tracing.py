"""
Tests for LangFuse Tracing (Story 1.5, Story 2.8).

- AC 1.5.1: LangFuse 초기화
- AC 1.5.2: LLM 호출 자동 추적
- AC 1.5.5: 비활성화 모드
- AC 2.8.10: extract_trace_context (TraceContext 추출)
"""

import logging
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.workflows.shared.tracing_utils import (
    TraceContext,
    _extract_trace_id,
    _find_langfuse_handler,
    extract_trace_context,
)


class TestTracingManagerDisabled:
    """Test tracing when LangFuse is not configured (AC 1.5.5)."""

    def test_tracing_disabled_when_no_keys(self) -> None:
        """LangFuse 환경 변수가 없으면 추적이 비활성화된다."""
        with patch("app.core.tracing.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            # 새로운 TracingManager 인스턴스 생성
            from app.core.tracing import TracingManager

            manager = TracingManager()
            manager.initialize()

            assert manager.enabled is False

    def test_tracing_logs_warning_when_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """비활성화 시 경고 로그가 출력된다."""
        with patch("app.core.tracing.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            from app.core.tracing import TracingManager

            manager = TracingManager()
            with caplog.at_level(logging.WARNING):
                manager.initialize()

            assert "LangFuse not configured, tracing disabled" in caplog.text

    def test_get_callback_handler_returns_none_when_disabled(self) -> None:
        """비활성화 시 콜백 핸들러가 None을 반환한다."""
        with patch("app.core.tracing.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            from app.core.tracing import TracingManager

            manager = TracingManager()
            handler = manager.get_callback_handler()

            assert handler is None

    def test_get_callbacks_returns_empty_list_when_disabled(self) -> None:
        """비활성화 시 빈 콜백 리스트를 반환한다."""
        with patch("app.core.tracing.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            from app.core.tracing import TracingManager

            manager = TracingManager()
            callbacks = manager.get_callbacks()

            assert callbacks == []


class TestTracingManagerEnabled:
    """Test tracing when LangFuse is configured (AC 1.5.1, AC 1.5.2)."""

    def test_tracing_enabled_with_valid_keys(self) -> None:
        """LangFuse 환경 변수가 있으면 추적이 활성화된다."""
        # Mock langfuse module
        mock_langfuse = MagicMock()
        with patch.dict(sys.modules, {"langfuse": mock_langfuse}):
            with patch("app.core.tracing.settings") as mock_settings:
                mock_settings.langfuse_enabled = True
                mock_settings.LANGFUSE_PUBLIC_KEY = "pk-test"
                mock_settings.LANGFUSE_SECRET_KEY = "sk-test"
                mock_settings.LANGFUSE_HOST = "https://cloud.langfuse.com"

                from app.core.tracing import TracingManager

                manager = TracingManager()
                manager.initialize()

                assert manager.enabled is True

    def test_get_callback_handler_creates_handler(self) -> None:
        """활성화 시 콜백 핸들러가 생성된다."""
        # Mock langfuse.langchain module
        mock_handler_instance = MagicMock()
        mock_callback_module = MagicMock()
        mock_callback_module.CallbackHandler.return_value = mock_handler_instance

        mock_langfuse = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "langfuse": mock_langfuse,
                "langfuse.langchain": mock_callback_module,
            },
        ):
            with patch("app.core.tracing.settings") as mock_settings:
                mock_settings.langfuse_enabled = True
                mock_settings.LANGFUSE_PUBLIC_KEY = "pk-test"
                mock_settings.LANGFUSE_SECRET_KEY = "sk-test"
                mock_settings.LANGFUSE_HOST = "https://cloud.langfuse.com"

                from app.core.tracing import TracingManager

                manager = TracingManager()
                handler = manager.get_callback_handler()

                assert handler is mock_handler_instance

    def test_get_callbacks_returns_list_with_handler(self) -> None:
        """활성화 시 콜백 리스트에 핸들러가 포함된다."""
        mock_handler_instance = MagicMock()
        mock_callback_module = MagicMock()
        mock_callback_module.CallbackHandler.return_value = mock_handler_instance

        mock_langfuse = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "langfuse": mock_langfuse,
                "langfuse.langchain": mock_callback_module,
            },
        ):
            with patch("app.core.tracing.settings") as mock_settings:
                mock_settings.langfuse_enabled = True
                mock_settings.LANGFUSE_PUBLIC_KEY = "pk-test"
                mock_settings.LANGFUSE_SECRET_KEY = "sk-test"
                mock_settings.LANGFUSE_HOST = "https://cloud.langfuse.com"

                from app.core.tracing import TracingManager

                manager = TracingManager()
                callbacks = manager.get_callbacks()

                assert len(callbacks) == 1
                assert callbacks[0] is mock_handler_instance


class TestTracingManagerMetadata:
    """Test metadata handling (AC 1.5.4) - SDK v3 방식.

    SDK v3에서는 session_id, user_id 등을 CallbackHandler에 직접 전달하지 않고
    get_langfuse_config()를 통해 config metadata로 전달합니다.
    """

    def test_get_langfuse_config_includes_session_id(self) -> None:
        """get_langfuse_config()이 session_id를 metadata에 포함한다."""
        mock_callback_module = MagicMock()
        mock_langfuse = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "langfuse": mock_langfuse,
                "langfuse.langchain": mock_callback_module,
            },
        ):
            with patch("app.core.tracing.settings") as mock_settings:
                mock_settings.langfuse_enabled = True
                mock_settings.LANGFUSE_PUBLIC_KEY = "pk-test"
                mock_settings.LANGFUSE_SECRET_KEY = "sk-test"
                mock_settings.LANGFUSE_HOST = "https://cloud.langfuse.com"

                from app.core.tracing import TracingManager

                manager = TracingManager()
                config = manager.get_langfuse_config(
                    session_id="session-123",
                    user_id="user-456",
                    metadata={"custom": "value"},
                )

                # SDK v3: langfuse_ 접두사로 metadata에 포함
                assert config["metadata"]["langfuse_session_id"] == "session-123"
                assert config["metadata"]["langfuse_user_id"] == "user-456"
                assert config["metadata"]["custom"] == "value"
                assert "callbacks" in config

    def test_get_langfuse_config_includes_tags(self) -> None:
        """get_langfuse_config()이 tags를 metadata에 포함한다."""
        mock_callback_module = MagicMock()
        mock_langfuse = MagicMock()

        with patch.dict(
            sys.modules,
            {
                "langfuse": mock_langfuse,
                "langfuse.langchain": mock_callback_module,
            },
        ):
            with patch("app.core.tracing.settings") as mock_settings:
                mock_settings.langfuse_enabled = True
                mock_settings.LANGFUSE_PUBLIC_KEY = "pk-test"
                mock_settings.LANGFUSE_SECRET_KEY = "sk-test"
                mock_settings.LANGFUSE_HOST = "https://cloud.langfuse.com"

                from app.core.tracing import TracingManager

                manager = TracingManager()
                config = manager.get_langfuse_config(
                    session_id="session-abc",
                    tags=["tag1", "tag2"],
                )

                assert config["metadata"]["langfuse_session_id"] == "session-abc"
                assert config["metadata"]["langfuse_tags"] == ["tag1", "tag2"]


class TestTracingInitialization:
    """Test initialization behavior."""

    def test_initialize_only_runs_once(self) -> None:
        """initialize()는 한 번만 실행된다."""
        with patch("app.core.tracing.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            from app.core.tracing import TracingManager

            manager = TracingManager()
            manager.initialize()
            manager.initialize()  # 두 번째 호출

            assert manager._initialized is True

    def test_enabled_property_triggers_initialization(self) -> None:
        """enabled 프로퍼티 접근 시 초기화가 트리거된다."""
        with patch("app.core.tracing.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            from app.core.tracing import TracingManager

            manager = TracingManager()
            assert manager._initialized is False

            # enabled 접근 시 초기화 발생
            _ = manager.enabled
            assert manager._initialized is True


class TestTraceContext:
    """TraceContext dataclass 테스트."""

    def test_default_values(self) -> None:
        """기본값은 모두 None."""
        ctx = TraceContext()
        assert ctx.trace_id is None
        assert ctx.observation_id is None

    def test_with_values(self) -> None:
        """값 설정 확인."""
        ctx = TraceContext(trace_id="abc123", observation_id="obs456")
        assert ctx.trace_id == "abc123"
        assert ctx.observation_id == "obs456"


class TestFindLangfuseHandler:
    """_find_langfuse_handler 테스트."""

    def test_finds_sdk_v3_handler(self) -> None:
        """last_trace_id 속성이 있는 handler를 찾는다 (SDK v3)."""
        handler = MagicMock(spec=["last_trace_id"])
        handler.last_trace_id = "trace-123"
        result = _find_langfuse_handler([handler])
        assert result is handler

    def test_finds_sdk_v2_handler(self) -> None:
        """get_trace_id 메서드가 있는 handler를 찾는다 (SDK v2)."""
        handler = MagicMock(spec=["get_trace_id"])
        result = _find_langfuse_handler([handler])
        assert result is handler

    def test_skips_non_langfuse_handlers(self) -> None:
        """LangFuse가 아닌 handler는 건너뛴다."""
        other_handler = MagicMock(spec=["on_llm_start"])
        result = _find_langfuse_handler([other_handler])
        assert result is None

    def test_returns_none_for_empty_list(self) -> None:
        """빈 리스트에서는 None 반환."""
        result = _find_langfuse_handler([])
        assert result is None

    def test_handles_non_iterable(self) -> None:
        """iterable이 아닌 경우 None 반환."""
        result = _find_langfuse_handler(None)
        assert result is None


class TestExtractTraceId:
    """_extract_trace_id 테스트."""

    def test_sdk_v2_get_trace_id(self) -> None:
        """SDK v2: get_trace_id() 메서드 사용."""
        handler = MagicMock(spec=["get_trace_id"])
        handler.get_trace_id.return_value = "trace-v2"
        assert _extract_trace_id(handler) == "trace-v2"

    def test_sdk_v2_trace_id_attr(self) -> None:
        """SDK v2: trace_id 속성 사용."""
        handler = MagicMock(spec=["trace_id"])
        handler.trace_id = "trace-v2-attr"
        assert _extract_trace_id(handler) == "trace-v2-attr"

    def test_sdk_v3_last_trace_id(self) -> None:
        """SDK v3: last_trace_id 속성 사용."""
        handler = MagicMock(spec=["last_trace_id"])
        handler.last_trace_id = "trace-v3"
        assert _extract_trace_id(handler) == "trace-v3"

    def test_sdk_v3_last_trace_id_none(self) -> None:
        """SDK v3: last_trace_id가 None이면 None 반환."""
        handler = MagicMock(spec=["last_trace_id"])
        handler.last_trace_id = None
        assert _extract_trace_id(handler) is None

    def test_no_trace_id_available(self) -> None:
        """trace_id를 추출할 수 없으면 None 반환."""
        handler = MagicMock(spec=["on_llm_start"])
        assert _extract_trace_id(handler) is None


class TestExtractTraceContext:
    """extract_trace_context 통합 테스트 (AC 2.8.10)."""

    def test_empty_config(self) -> None:
        """빈 config에서는 빈 TraceContext 반환."""
        ctx = extract_trace_context({})
        assert ctx.trace_id is None
        assert ctx.observation_id is None

    def test_no_callbacks(self) -> None:
        """callbacks가 None이면 빈 TraceContext 반환."""
        ctx = extract_trace_context({"callbacks": None})
        assert ctx.trace_id is None
        assert ctx.observation_id is None

    def _make_handler(self, *, last_trace_id="trace-abc", runs=None):
        """SDK v3 스타일 LangFuse handler mock 생성."""
        handler = MagicMock(spec=["last_trace_id", "runs"])
        handler.last_trace_id = last_trace_id
        handler.runs = runs or {}
        return handler

    def _make_manager(self, handler, *, parent_run_id=None):
        """CallbackManager mock 생성."""
        manager = MagicMock(spec=["handlers", "parent_run_id"])
        manager.handlers = [handler]
        manager.parent_run_id = parent_run_id
        return manager

    def test_extracts_trace_id_from_handler(self) -> None:
        """handler에서 trace_id를 추출한다."""
        handler = self._make_handler(last_trace_id="trace-abc")
        manager = self._make_manager(handler)

        ctx = extract_trace_context({"callbacks": manager})
        assert ctx.trace_id == "trace-abc"
        assert ctx.observation_id is None

    def test_extracts_both_trace_id_and_observation_id(self) -> None:
        """trace_id와 observation_id 모두 추출한다."""
        parent_run_id = uuid4()
        obs = MagicMock()
        obs.id = "obs-123"

        handler = self._make_handler(
            last_trace_id="trace-xyz",
            runs={parent_run_id: obs},
        )
        manager = self._make_manager(handler, parent_run_id=parent_run_id)

        ctx = extract_trace_context({"callbacks": manager})
        assert ctx.trace_id == "trace-xyz"
        assert ctx.observation_id == "obs-123"

    def test_observation_id_none_when_no_parent_run(self) -> None:
        """parent_run_id가 없으면 observation_id는 None."""
        handler = self._make_handler(last_trace_id="trace-no-parent")
        manager = self._make_manager(handler)

        ctx = extract_trace_context({"callbacks": manager})
        assert ctx.trace_id == "trace-no-parent"
        assert ctx.observation_id is None

    def test_observation_id_none_when_run_not_found(self) -> None:
        """parent_run_id에 해당하는 run이 없으면 observation_id는 None."""
        parent_run_id = uuid4()

        handler = self._make_handler(last_trace_id="trace-missing-run")
        manager = self._make_manager(handler, parent_run_id=parent_run_id)

        ctx = extract_trace_context({"callbacks": manager})
        assert ctx.trace_id == "trace-missing-run"
        assert ctx.observation_id is None
