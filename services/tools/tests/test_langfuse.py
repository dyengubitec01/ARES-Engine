"""Langfuse 연동 모듈 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from src.middleware.langfuse import (
    create_generation,
    create_span,
    flush_langfuse,
    get_langfuse_client,
)


@pytest.fixture(autouse=True)
def reset_langfuse_state():
    """각 테스트 전후로 상태 초기화."""
    get_langfuse_client.cache_clear()
    yield
    get_langfuse_client.cache_clear()


class TestGetLangfuseClient:
    """get_langfuse_client 함수 테스트."""

    def test_returns_none_when_no_keys(self):
        """환경변수 미설정 시 None 반환 테스트."""
        with patch("src.middleware.langfuse.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                langfuse_public_key="",
                langfuse_secret_key="",
                langfuse_host="",
            )
            result = get_langfuse_client()
            assert result is None

    def test_returns_client_when_keys_provided(self):
        """환경변수 설정 시 클라이언트 반환 테스트."""
        with (
            patch("src.middleware.langfuse.get_settings") as mock_settings,
            patch("src.middleware.langfuse.Langfuse") as mock_langfuse,
        ):
            mock_settings.return_value = MagicMock(
                langfuse_public_key="pk-test",
                langfuse_secret_key="sk-test",
                langfuse_host="https://langfuse.example.com",
            )
            mock_client = MagicMock()
            mock_langfuse.return_value = mock_client

            result = get_langfuse_client()

            assert result == mock_client
            mock_langfuse.assert_called_once_with(
                public_key="pk-test",
                secret_key="sk-test",
                host="https://langfuse.example.com",
            )

    def test_returns_none_on_init_error(self):
        """클라이언트 초기화 실패 시 None 반환 테스트."""
        with (
            patch("src.middleware.langfuse.get_settings") as mock_settings,
            patch("src.middleware.langfuse.Langfuse") as mock_langfuse,
        ):
            mock_settings.return_value = MagicMock(
                langfuse_public_key="pk-test",
                langfuse_secret_key="sk-test",
                langfuse_host="",
            )
            mock_langfuse.side_effect = Exception("Connection failed")

            result = get_langfuse_client()
            assert result is None


class TestCreateSpan:
    """create_span 함수 테스트."""

    def test_returns_none_when_no_trace_context(self):
        """trace_context 없으면 None 반환 (독립 observation 방지)."""
        result = create_span("test-span")
        assert result is None

    def test_returns_none_when_no_client(self):
        """클라이언트 없을 때 None 반환 테스트."""
        with patch(
            "src.middleware.langfuse.get_langfuse_client", return_value=None
        ):
            result = create_span(
                "test-span",
                trace_context={"trace_id": "abc123"},
            )
            assert result is None

    def test_creates_managed_span_with_trace_context(self):
        """trace_context 전달 시 ManagedSpan 래퍼 반환."""
        from src.middleware.langfuse import ManagedSpan

        mock_client = MagicMock()
        mock_span = MagicMock()
        mock_span._otel_span = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_span)
        mock_client.start_as_current_observation.return_value = mock_cm

        trace_ctx = {"trace_id": "abc123", "parent_span_id": "span456"}

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            result = create_span(
                "test-span",
                input_data={"input": "data"},
                metadata={"key": "value"},
                trace_context=trace_ctx,
            )

            assert isinstance(result, ManagedSpan)
            mock_client.start_as_current_observation.assert_called_once_with(
                as_type="span",
                name="test-span",
                trace_context=trace_ctx,
                input={"input": "data"},
                metadata={"key": "value"},
            )

    def test_managed_span_end_calls_cm_exit(self):
        """ManagedSpan.end()가 cm.__exit__()를 호출하는지 검증."""
        mock_span = MagicMock()
        mock_span._otel_span = MagicMock()
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_span)
        mock_client = MagicMock()
        mock_client.start_as_current_observation.return_value = mock_cm

        trace_ctx = {"trace_id": "abc123"}

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            managed = create_span("test", trace_context=trace_ctx)
            managed.update(output="test output")
            managed.end()

            mock_span.update.assert_called_once_with(output="test output")
            mock_cm.__exit__.assert_called_once_with(None, None, None)

    def test_returns_none_on_error(self):
        """span 생성 실패 시 None 반환 테스트."""
        mock_client = MagicMock()
        mock_client.start_as_current_observation.side_effect = Exception("API Error")

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            result = create_span(
                "test-span",
                trace_context={"trace_id": "abc123"},
            )
            assert result is None


class TestCreateGeneration:
    """create_generation 함수 테스트."""

    def test_returns_none_when_no_trace_context(self):
        """trace_context 없으면 None 반환 (독립 observation 방지)."""
        result = create_generation("test-gen", "gpt-4o")
        assert result is None

    def test_returns_none_when_no_client(self):
        """클라이언트 없을 때 None 반환 테스트."""
        with patch(
            "src.middleware.langfuse.get_langfuse_client", return_value=None
        ):
            result = create_generation(
                "test-gen", "gpt-4o",
                trace_context={"trace_id": "abc123"},
            )
            assert result is None

    def test_creates_generation_successfully(self):
        """generation 생성 성공 테스트 (SDK v3: client.start_observation)."""
        mock_client = MagicMock()
        mock_generation = MagicMock()
        mock_client.start_observation.return_value = mock_generation

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            result = create_generation(
                "test-gen",
                model="gpt-4o",
                input_data={"messages": []},
                output_data="response",
                metadata={"key": "value"},
                trace_context={"trace_id": "abc123"},
            )

            assert result == mock_generation
            mock_client.start_observation.assert_called_once_with(
                name="test-gen",
                as_type="generation",
                model="gpt-4o",
                input={"messages": []},
                output="response",
                metadata={"key": "value"},
            )

    def test_returns_none_on_error(self):
        """generation 생성 실패 시 None 반환 테스트."""
        mock_client = MagicMock()
        mock_client.start_observation.side_effect = Exception("API Error")

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            result = create_generation(
                "test-gen", "gpt-4o",
                trace_context={"trace_id": "abc123"},
            )
            assert result is None


class TestFlushLangfuse:
    """flush_langfuse 함수 테스트."""

    def test_does_nothing_when_no_client(self):
        """클라이언트 없을 때 아무것도 안함 테스트."""
        with patch(
            "src.middleware.langfuse.get_langfuse_client", return_value=None
        ):
            # 예외 없이 완료되어야 함
            flush_langfuse()

    def test_flushes_client(self):
        """클라이언트 flush 호출 테스트."""
        mock_client = MagicMock()
        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            flush_langfuse()
            mock_client.flush.assert_called_once()

    def test_handles_flush_error(self):
        """flush 실패 시 예외 처리 테스트."""
        mock_client = MagicMock()
        mock_client.flush.side_effect = Exception("Flush failed")
        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            # 예외 없이 완료되어야 함
            flush_langfuse()
