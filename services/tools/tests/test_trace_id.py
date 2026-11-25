"""Trace-ID 미들웨어 테스트."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.middleware.trace_id import (
    PARENT_ID_HEADER,
    TRACE_ID_HEADER,
    generate_trace_id,
    get_trace_id,
    trace_id_var,
)


@pytest.fixture
def client():
    """FastAPI 테스트 클라이언트."""
    return TestClient(app)


class TestGenerateTraceId:
    """generate_trace_id 함수 테스트."""

    def test_returns_string(self):
        """문자열 반환 테스트."""
        trace_id = generate_trace_id()
        assert isinstance(trace_id, str)

    def test_returns_valid_uuid(self):
        """유효한 UUID 반환 테스트."""
        trace_id = generate_trace_id()
        # UUID 형식 검증
        parsed = uuid.UUID(trace_id)
        assert str(parsed) == trace_id

    def test_returns_unique_ids(self):
        """고유 ID 반환 테스트."""
        ids = [generate_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestGetTraceId:
    """get_trace_id 함수 테스트."""

    def test_returns_none_by_default(self):
        """기본값 None 반환 테스트."""
        # ContextVar 초기화
        trace_id_var.set(None)
        assert get_trace_id() is None

    def test_returns_set_value(self):
        """설정된 값 반환 테스트."""
        test_id = "test-trace-id-123"
        token = trace_id_var.set(test_id)
        try:
            assert get_trace_id() == test_id
        finally:
            trace_id_var.reset(token)


class TestTraceIDMiddleware:
    """TraceIDMiddleware 테스트."""

    def test_generates_trace_id_when_missing(self, client):
        """헤더 없을 때 Trace-ID 자동 생성 테스트."""
        response = client.get("/health")

        assert response.status_code == 200
        assert TRACE_ID_HEADER in response.headers

        # UUID 형식 검증
        trace_id = response.headers[TRACE_ID_HEADER]
        uuid.UUID(trace_id)  # 유효하지 않으면 예외 발생

    def test_uses_provided_trace_id(self, client):
        """헤더로 전달된 Trace-ID 사용 테스트."""
        custom_trace_id = "custom-trace-id-456"
        response = client.get(
            "/health",
            headers={TRACE_ID_HEADER: custom_trace_id},
        )

        assert response.status_code == 200
        assert response.headers[TRACE_ID_HEADER] == custom_trace_id

    def test_generated_header_flag(self, client):
        """자동 생성 시 플래그 헤더 테스트."""
        response = client.get("/health")

        assert response.headers.get("X-LF-Trace-ID-Generated") == "true"

    def test_no_generated_flag_when_provided(self, client):
        """헤더 제공 시 플래그 없음 테스트."""
        response = client.get(
            "/health",
            headers={TRACE_ID_HEADER: "provided-id"},
        )

        assert "X-LF-Trace-ID-Generated" not in response.headers

    def test_trace_id_header_name(self):
        """헤더 이름 상수 테스트."""
        assert TRACE_ID_HEADER == "X-LF-Trace-ID"


class TestHealthEndpointWithTraceID:
    """헬스체크 엔드포인트 + Trace-ID 통합 테스트."""

    def test_health_returns_trace_id(self, client):
        """헬스체크 응답에 Trace-ID 포함 테스트."""
        response = client.get("/health")

        assert response.status_code == 200
        assert TRACE_ID_HEADER in response.headers

        data = response.json()
        assert data["code"] == "TOL010100"
        assert data["data"]["status"] == "ok"

    def test_health_preserves_custom_trace_id(self, client):
        """커스텀 Trace-ID 보존 테스트."""
        custom_id = "my-custom-trace-12345"
        response = client.get(
            "/health",
            headers={TRACE_ID_HEADER: custom_id},
        )

        assert response.status_code == 200
        assert response.headers[TRACE_ID_HEADER] == custom_id


class TestHandleRequestLangfuseBranch:
    """_handle_request의 Langfuse root span 분기 테스트."""

    @pytest.fixture
    def client(self):
        """FastAPI 테스트 클라이언트."""
        return TestClient(app)

    def test_no_langfuse_client_skips_observation(self, client):
        """Langfuse 미설정 시 start_as_current_observation 호출 없이 정상 응답."""
        with patch(
            "src.middleware.langfuse.get_langfuse_client", return_value=None
        ):
            valid_uuid = str(uuid.uuid4())
            response = client.get(
                "/v1/tools",
                headers={
                    TRACE_ID_HEADER: valid_uuid,
                    "X-TOL-Scope": "agent",
                },
            )

            assert response.status_code == 200
            assert response.headers[TRACE_ID_HEADER] == valid_uuid

    def test_valid_uuid_trace_id_triggers_root_span(self, client):
        """에이전트가 유효 UUID trace-id를 넘기면 start_as_current_observation 호출."""
        mock_client = MagicMock()
        mock_root_span = MagicMock()
        mock_root_span._otel_span = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = (
            MagicMock(return_value=mock_root_span)
        )
        mock_client.start_as_current_observation.return_value.__exit__ = (
            MagicMock(return_value=False)
        )

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
            response = client.get(
                "/v1/tools",
                headers={
                    TRACE_ID_HEADER: valid_uuid,
                    "X-TOL-Scope": "agent",
                },
            )

            assert response.status_code == 200
            assert response.headers[TRACE_ID_HEADER] == valid_uuid

            mock_client.start_as_current_observation.assert_called_once()
            call_kwargs = (
                mock_client.start_as_current_observation.call_args.kwargs
            )
            assert call_kwargs["as_type"] == "span"
            assert call_kwargs["name"] == "http-request"
            # AC-3: 하이픈 제거 없이 원본 그대로 전달
            assert (
                call_kwargs["trace_context"]["trace_id"]
                == "550e8400-e29b-41d4-a716-446655440000"
            )

    def test_health_endpoint_skips_langfuse(self, client):
        """AC-2: /health 엔드포인트는 Langfuse trace를 생성하지 않는다."""
        mock_client = MagicMock()

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            valid_uuid = str(uuid.uuid4())
            response = client.get(
                "/health",
                headers={TRACE_ID_HEADER: valid_uuid},
            )

            assert response.status_code == 200
            assert response.headers[TRACE_ID_HEADER] == valid_uuid
            mock_client.start_as_current_observation.assert_not_called()

    def test_no_trace_header_skips_langfuse(self, client):
        """AC-1: X-LF-Trace-ID 헤더 없으면 Langfuse trace 미생성."""
        mock_client = MagicMock()

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            response = client.get("/health")

            assert response.status_code == 200
            assert response.headers.get("X-LF-Trace-ID-Generated") == "true"
            mock_client.start_as_current_observation.assert_not_called()

    def test_32char_hex_trace_id_accepted(self, client):
        """AC-3: 32자 hex trace_id도 유효하게 처리."""
        mock_client = MagicMock()
        mock_root_span = MagicMock()
        mock_root_span._otel_span = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = (
            MagicMock(return_value=mock_root_span)
        )
        mock_client.start_as_current_observation.return_value.__exit__ = (
            MagicMock(return_value=False)
        )

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            hex_id = "550e8400e29b41d4a716446655440000"
            response = client.get(
                "/v1/tools",
                headers={
                    TRACE_ID_HEADER: hex_id,
                    "X-TOL-Scope": "agent",
                },
            )

            assert response.status_code == 200
            mock_client.start_as_current_observation.assert_called_once()
            call_kwargs = (
                mock_client.start_as_current_observation.call_args.kwargs
            )
            assert call_kwargs["trace_context"]["trace_id"] == hex_id

    def test_non_hex_trace_id_skips_observation(self, client):
        """비-hex trace-id 전달 시 Langfuse 우회, 정상 응답."""
        mock_client = MagicMock()

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            response = client.get(
                "/v1/tools",
                headers={
                    TRACE_ID_HEADER: "not-a-valid-hex-id",
                    "X-TOL-Scope": "agent",
                },
            )

            assert response.status_code == 200
            assert (
                response.headers[TRACE_ID_HEADER] == "not-a-valid-hex-id"
            )
            mock_client.start_as_current_observation.assert_not_called()


class TestParentIdHeader:
    """X-LF-Parent-Id 헤더 전파 테스트."""

    @pytest.fixture
    def client(self):
        """FastAPI 테스트 클라이언트."""
        return TestClient(app)

    def test_parent_id_header_constant(self):
        """AC-4: PARENT_ID_HEADER 상수 확인."""
        assert PARENT_ID_HEADER == "X-LF-Parent-Id"

    def test_parent_id_passed_to_trace_context(self, client):
        """AC-5: parent_id가 trace_context에 parent_span_id로 전달."""
        mock_client = MagicMock()
        mock_root_span = MagicMock()
        mock_root_span._otel_span = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = (
            MagicMock(return_value=mock_root_span)
        )
        mock_client.start_as_current_observation.return_value.__exit__ = (
            MagicMock(return_value=False)
        )

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            trace_id = "550e8400-e29b-41d4-a716-446655440000"
            parent_id = "abcdef0123456789"
            response = client.get(
                "/v1/tools",
                headers={
                    TRACE_ID_HEADER: trace_id,
                    PARENT_ID_HEADER: parent_id,
                    "X-TOL-Scope": "agent",
                },
            )

            assert response.status_code == 200
            call_kwargs = (
                mock_client.start_as_current_observation.call_args.kwargs
            )
            assert call_kwargs["trace_context"]["parent_span_id"] == parent_id

    def test_no_parent_id_works_without_parent_span_id(self, client):
        """AC-6: parent_id 없이도 정상 동작 (하위 호환)."""
        mock_client = MagicMock()
        mock_root_span = MagicMock()
        mock_root_span._otel_span = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = (
            MagicMock(return_value=mock_root_span)
        )
        mock_client.start_as_current_observation.return_value.__exit__ = (
            MagicMock(return_value=False)
        )

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            trace_id = "550e8400-e29b-41d4-a716-446655440000"
            response = client.get(
                "/v1/tools",
                headers={
                    TRACE_ID_HEADER: trace_id,
                    "X-TOL-Scope": "agent",
                },
            )

            assert response.status_code == 200
            call_kwargs = (
                mock_client.start_as_current_observation.call_args.kwargs
            )
            assert "parent_span_id" not in call_kwargs["trace_context"]


class TestStripAsRoot:
    """AC-7: _strip_as_root 래퍼로 trace name 덮어쓰기 방지 테스트."""

    @pytest.fixture
    def client(self):
        """FastAPI 테스트 클라이언트."""
        return TestClient(app)

    def test_strip_as_root_called(self, client):
        """root span 생성 후 as_root=False로 설정되는지 확인."""
        mock_client = MagicMock()
        mock_root_span = MagicMock()
        mock_otel_span = MagicMock()
        mock_root_span._otel_span = mock_otel_span
        mock_client.start_as_current_observation.return_value.__enter__ = (
            MagicMock(return_value=mock_root_span)
        )
        mock_client.start_as_current_observation.return_value.__exit__ = (
            MagicMock(return_value=False)
        )

        with patch(
            "src.middleware.langfuse.get_langfuse_client",
            return_value=mock_client,
        ):
            trace_id = str(uuid.uuid4())
            response = client.get(
                "/v1/tools",
                headers={
                    TRACE_ID_HEADER: trace_id,
                    "X-TOL-Scope": "agent",
                },
            )

            assert response.status_code == 200
            mock_otel_span.set_attribute.assert_called_with(
                "langfuse.internal.as_root", False
            )
