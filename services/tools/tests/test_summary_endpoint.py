"""요약 엔드포인트 테스트.

Router → Service → Provider 통합 및 TOL 표준 응답 검증.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.providers.deps import get_llm_provider
from src.schemas.codes import TOLCode, TOLMessage


# --- 공통 상수 ---

VALID_SCOPE_HEADER = {"X-TOL-Scope": "agent"}

VALID_REQUEST_BODY = {
    "history": [
        {"role": "user", "content": "안녕"},
        {"role": "assistant", "content": "안녕하세요!"},
    ],
}

VALID_REQUEST_BODY_WITH_SUMMARY = {
    "summary": "이전 요약 내용",
    "history": [
        {"role": "user", "content": "안녕"},
        {"role": "assistant", "content": "안녕하세요!"},
    ],
}

# --- OpenAI 응답 fixture ---

MOCK_LLM_RESPONSE = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "요약된 텍스트입니다.",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
    },
}


@pytest.fixture()
def mock_provider():
    """LLM Provider mock fixture."""
    provider = AsyncMock()
    provider.invoke_with_failover = AsyncMock(return_value=MOCK_LLM_RESPONSE)
    return provider


@pytest.fixture()
def client(mock_provider):
    """Provider를 mock으로 교체한 TestClient (FastAPI DI override)."""
    app.dependency_overrides[get_llm_provider] = lambda: mock_provider
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# --- 정상 응답 테스트 ---


class TestSummaryEndpointSuccess:
    """POST /v1/summary 정상 응답 테스트."""

    def test_returns_200_with_tol_response(self, client):
        """정상 요청 시 200 + TOL 표준 응답."""
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers=VALID_SCOPE_HEADER,
        )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == TOLCode.SUCCESS_SUMMARY.value
        assert body["msg"] == TOLMessage.SUCCESS.value

    def test_response_contains_summary_data(self, client):
        """응답 data에 summary 필드 포함."""
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers=VALID_SCOPE_HEADER,
        )

        body = response.json()
        assert "data" in body
        assert body["data"]["summary"] == "요약된 텍스트입니다."

    def test_provider_called_with_messages(self, client, mock_provider):
        """Provider가 system + user(대화내용) 메시지로 호출됨."""
        client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers=VALID_SCOPE_HEADER,
        )

        mock_provider.invoke_with_failover.assert_called_once()
        call_kwargs = mock_provider.invoke_with_failover.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[1]

        # system + user(대화내용 통합) = 2 메시지
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "[대화 내용]" in messages[1]["content"]
        assert "user: 안녕" in messages[1]["content"]
        assert "assistant: 안녕하세요!" in messages[1]["content"]

    def test_provider_called_with_summary_context(self, client, mock_provider):
        """이전 summary 전달 시 메시지에 포함."""
        client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY_WITH_SUMMARY,
            headers=VALID_SCOPE_HEADER,
        )

        call_kwargs = mock_provider.invoke_with_failover.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[1]

        # system + user(이전요약 + 대화내용) = 2 메시지
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        # user 메시지에 이전 요약과 대화 내용이 모두 포함
        assert "[이전 요약]" in messages[1]["content"]
        assert "이전 요약 내용" in messages[1]["content"]
        assert "[대화 내용]" in messages[1]["content"]

    def test_system_prompt_contains_token_count(self, client, mock_provider):
        """시스템 프롬프트에 target_n_tokens 값이 주입됨."""
        client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers=VALID_SCOPE_HEADER,
        )

        call_kwargs = mock_provider.invoke_with_failover.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[1]
        system_content = messages[0]["content"]

        assert "{target_n_tokens}" not in system_content
        assert "300" in system_content

    def test_response_has_trace_id_header(self, client):
        """응답에 X-LF-Trace-ID 헤더 포함."""
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers=VALID_SCOPE_HEADER,
        )

        assert "x-lf-trace-id" in response.headers

    def test_request_trace_id_echoed_in_response(self, client):
        """요청 Trace-ID가 응답에 동일하게 포함."""
        trace_id = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers={**VALID_SCOPE_HEADER, "X-LF-Trace-ID": trace_id},
        )

        assert response.headers.get("x-lf-trace-id") == trace_id


# --- 입력 검증 테스트 ---


class TestSummaryEndpointValidation:
    """POST /v1/summary 입력 검증 테스트."""

    def test_missing_history_returns_422(self, client):
        """history 필드 누락 시 422."""
        response = client.post(
            "/v1/summary",
            json={},
            headers=VALID_SCOPE_HEADER,
        )
        assert response.status_code == 422

    def test_empty_history_returns_422(self, client):
        """빈 배열 history 시 422."""
        response = client.post(
            "/v1/summary",
            json={"history": []},
            headers=VALID_SCOPE_HEADER,
        )
        assert response.status_code == 422

    def test_no_body_returns_422(self, client):
        """요청 본문 없을 시 422."""
        response = client.post(
            "/v1/summary",
            headers=VALID_SCOPE_HEADER,
        )
        assert response.status_code == 422

    def test_empty_role_returns_422(self, client):
        """role 빈 문자열 시 422."""
        response = client.post(
            "/v1/summary",
            json={"history": [{"role": "", "content": "안녕"}]},
            headers=VALID_SCOPE_HEADER,
        )
        assert response.status_code == 422

    def test_empty_content_returns_422(self, client):
        """content 빈 문자열 시 422."""
        response = client.post(
            "/v1/summary",
            json={"history": [{"role": "user", "content": ""}]},
            headers=VALID_SCOPE_HEADER,
        )
        assert response.status_code == 422

    def test_invalid_role_returns_422(self, client):
        """허용되지 않은 role 값 시 422."""
        response = client.post(
            "/v1/summary",
            json={"history": [{"role": "admin", "content": "테스트"}]},
            headers=VALID_SCOPE_HEADER,
        )
        assert response.status_code == 422

    def test_empty_summary_returns_422(self, client):
        """summary 빈 문자열 시 422."""
        response = client.post(
            "/v1/summary",
            json={"summary": "", "history": [{"role": "user", "content": "안녕"}]},
            headers=VALID_SCOPE_HEADER,
        )
        assert response.status_code == 422

    def test_summary_without_history_returns_422(self, client):
        """summary만 있고 history 없으면 422."""
        response = client.post(
            "/v1/summary",
            json={"summary": "이전 요약"},
            headers=VALID_SCOPE_HEADER,
        )
        assert response.status_code == 422

    def test_summary_optional_succeeds_without_it(self, client):
        """summary 없이 history만 전달해도 정상."""
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers=VALID_SCOPE_HEADER,
        )
        assert response.status_code == 200

    def test_summary_with_history_succeeds(self, client):
        """summary + history 전달 시 정상."""
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY_WITH_SUMMARY,
            headers=VALID_SCOPE_HEADER,
        )
        assert response.status_code == 200


# --- Scope 검증 테스트 ---


class TestSummaryEndpointScopeValidation:
    """POST /v1/summary Scope 접근 제어 테스트."""

    def test_missing_scope_returns_400(self, client):
        """X-TOL-Scope 헤더 미전달 시 400."""
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
        )

        assert response.status_code == 400
        body = response.json()
        assert body["code"] == TOLCode.ERROR_INVALID_SCOPE.value
        assert body["msg"] == TOLMessage.INVALID_SCOPE.value

    def test_disallowed_scope_returns_400(self, client):
        """summary에 허용되지 않은 Scope(frontend) → 400."""
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers={"X-TOL-Scope": "frontend"},
        )

        assert response.status_code == 400
        body = response.json()
        assert body["code"] == TOLCode.ERROR_INVALID_SCOPE.value

    def test_invalid_scope_returns_400(self, client):
        """존재하지 않는 Scope → 400."""
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers={"X-TOL-Scope": "unknown"},
        )

        assert response.status_code == 400

    def test_agent_scope_allowed(self, client):
        """agent Scope → 정상 처리."""
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers={"X-TOL-Scope": "agent"},
        )

        assert response.status_code == 200

    def test_backend_scope_allowed(self, client):
        """backend Scope → 정상 처리."""
        response = client.post(
            "/v1/summary",
            json=VALID_REQUEST_BODY,
            headers={"X-TOL-Scope": "backend"},
        )

        assert response.status_code == 200


# --- Graceful Degradation 테스트 ---


class TestSummaryEndpointGracefulDegradation:
    """Provider 전체 실패 시 Graceful Degradation 테스트."""

    def test_provider_failure_returns_503(self):
        """Provider 전체 실패 시 503 + TOL020130."""
        from src.exceptions.exceptions import LLMProviderError

        failing_provider = AsyncMock()
        failing_provider.invoke_with_failover = AsyncMock(
            side_effect=LLMProviderError(
                detail="AI 서비스 이용 불가",
                role="primary",
                chain=["primary", "fast"],
            ),
        )

        app.dependency_overrides[get_llm_provider] = lambda: failing_provider
        try:
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/v1/summary",
                json=VALID_REQUEST_BODY,
                headers=VALID_SCOPE_HEADER,
            )

            assert response.status_code == 503
            body = response.json()
            assert body["code"] == TOLCode.ERROR_LLM_CONNECTION.value
        finally:
            app.dependency_overrides.clear()


# --- Service 단위 테스트 ---


class TestSummarizeService:
    """summarize() 서비스 함수 단위 테스트."""

    @pytest.mark.asyncio
    async def test_summarize_returns_content(self):
        """summarize()가 LLM 응답에서 content를 추출."""
        from src.schemas.summary import ChatMessage
        from src.services.summary import summarize

        provider = AsyncMock()
        provider.invoke_with_failover = AsyncMock(
            return_value=MOCK_LLM_RESPONSE,
        )

        history = [ChatMessage(role="user", content="테스트 텍스트")]
        result = await summarize(history, provider)
        assert result == "요약된 텍스트입니다."

    @pytest.mark.asyncio
    async def test_summarize_calls_provider_with_primary_role(self):
        """summarize()가 Provider를 primary 역할로 호출."""
        from src.schemas.summary import ChatMessage
        from src.services.summary import summarize

        provider = AsyncMock()
        provider.invoke_with_failover = AsyncMock(
            return_value=MOCK_LLM_RESPONSE,
        )

        history = [ChatMessage(role="user", content="텍스트")]
        await summarize(history, provider)

        call_kwargs = provider.invoke_with_failover.call_args
        assert call_kwargs.kwargs["role"] == "primary"

    @pytest.mark.asyncio
    async def test_summarize_passes_trace_metadata(self):
        """summarize()가 trace_metadata를 Provider에 전달."""
        from src.schemas.summary import ChatMessage
        from src.services.summary import summarize

        provider = AsyncMock()
        provider.invoke_with_failover = AsyncMock(
            return_value=MOCK_LLM_RESPONSE,
        )
        metadata = {"request_id": "test-123"}
        history = [ChatMessage(role="user", content="텍스트")]

        await summarize(history, provider, trace_metadata=metadata)

        call_kwargs = provider.invoke_with_failover.call_args
        assert call_kwargs.kwargs["trace_metadata"] == metadata

    @pytest.mark.asyncio
    async def test_summarize_with_previous_summary(self):
        """이전 summary 전달 시 메시지에 포함."""
        from src.schemas.summary import ChatMessage
        from src.services.summary import summarize

        provider = AsyncMock()
        provider.invoke_with_failover = AsyncMock(
            return_value=MOCK_LLM_RESPONSE,
        )

        history = [ChatMessage(role="user", content="텍스트")]
        await summarize(history, provider, summary="이전 요약")

        call_kwargs = provider.invoke_with_failover.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[1]
        # system + user(이전요약 + 대화내용) = 2 메시지
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "[이전 요약]" in messages[1]["content"]
        assert "이전 요약" in messages[1]["content"]
        assert "[대화 내용]" in messages[1]["content"]
        assert "user: 텍스트" in messages[1]["content"]
