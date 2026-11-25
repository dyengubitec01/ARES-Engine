"""LLM Provider 테스트.

respx 기반 httpx mock 테스트.
정상 호출, 에러 응답, 타임아웃 시나리오.
"""

import json

import httpx
import pytest
import respx

from src.config.models import load_models_config
from src.exceptions.exceptions import LLMProviderError
from src.providers.base import BaseLLMProvider
from src.providers.gateway import GatewayLLMProvider, create_gateway_provider

# models.yaml에서 기대 모델명 로드 — 하드코딩 방지
_models_cfg = load_models_config()
_PRIMARY_MODEL = _models_cfg.get_model("primary")
_FAST_MODEL = _models_cfg.get_model("fast")

# --- Fixtures ---

GATEWAY_URL = "http://test-gateway:4000/v1"
API_KEY = "test-api-key"
CHAT_COMPLETIONS_URL = f"{GATEWAY_URL}/chat/completions"

SAMPLE_MESSAGES: list[dict[str, str]] = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello"},
]

OPENAI_SUCCESS_RESPONSE: dict = {
    "id": "chatcmpl-test123",
    "object": "chat.completion",
    "created": 1700000000,
    "model": _PRIMARY_MODEL,
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! How can I help you?",
            },
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 20,
        "completion_tokens": 10,
        "total_tokens": 30,
    },
}


@pytest.fixture
def provider() -> GatewayLLMProvider:
    """테스트용 GatewayLLMProvider 인스턴스."""
    return GatewayLLMProvider(
        gateway_url=GATEWAY_URL,
        api_key=API_KEY,
        max_tokens=512,
        temperature=0.4,
        default_timeout=30.0,
    )


@pytest.fixture(autouse=True)
def clear_models_cache():
    """각 테스트마다 모델 설정 캐시 클리어."""
    load_models_config.cache_clear()
    yield
    load_models_config.cache_clear()


# --- BaseLLMProvider ABC 테스트 ---


class TestBaseLLMProvider:
    """BaseLLMProvider ABC 테스트."""

    def test_cannot_instantiate_abc(self):
        """ABC 직접 인스턴스화 불가 테스트."""
        with pytest.raises(TypeError):
            BaseLLMProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_invoke(self):
        """invoke 미구현 시 인스턴스화 불가 테스트."""

        class IncompleteProvider(BaseLLMProvider):
            async def invoke_with_failover(
                self, role, messages, max_retries=1, *, trace_metadata=None
            ):
                return {}

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_subclass_must_implement_invoke_with_failover(self):
        """invoke_with_failover 미구현 시 인스턴스화 불가 테스트."""

        class IncompleteProvider(BaseLLMProvider):
            async def invoke(self, role, messages):
                return {}

        with pytest.raises(TypeError):
            IncompleteProvider()  # type: ignore[abstract]

    def test_gateway_provider_is_subclass(self):
        """GatewayLLMProvider가 BaseLLMProvider의 서브클래스인지 테스트."""
        assert issubclass(GatewayLLMProvider, BaseLLMProvider)

    def test_gateway_provider_isinstance(self, provider: GatewayLLMProvider):
        """GatewayLLMProvider 인스턴스가 BaseLLMProvider인지 테스트."""
        assert isinstance(provider, BaseLLMProvider)


# --- GatewayLLMProvider invoke() 테스트 ---


class TestGatewayInvoke:
    """GatewayLLMProvider invoke() 테스트."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_success(self, provider: GatewayLLMProvider):
        """정상 호출 테스트."""
        route = respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(200, json=OPENAI_SUCCESS_RESPONSE)
        )

        result = await provider.invoke("primary", SAMPLE_MESSAGES)

        assert route.called
        assert result["id"] == "chatcmpl-test123"
        assert result["choices"][0]["message"]["content"] == "Hello! How can I help you?"

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_sends_correct_payload(self, provider: GatewayLLMProvider):
        """올바른 페이로드 전송 테스트."""
        route = respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(200, json=OPENAI_SUCCESS_RESPONSE)
        )

        await provider.invoke("primary", SAMPLE_MESSAGES)

        request = route.calls[0].request
        body = json.loads(request.content)
        assert body["model"] == _PRIMARY_MODEL
        assert body["messages"] == SAMPLE_MESSAGES
        assert body["max_tokens"] == 512
        assert body["temperature"] == 0.4

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_sends_auth_header(self, provider: GatewayLLMProvider):
        """Authorization 헤더 전송 테스트."""
        route = respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(200, json=OPENAI_SUCCESS_RESPONSE)
        )

        await provider.invoke("primary", SAMPLE_MESSAGES)

        request = route.calls[0].request
        assert request.headers["Authorization"] == f"Bearer {API_KEY}"
        assert request.headers["Content-Type"] == "application/json"

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_fast_role(self, provider: GatewayLLMProvider):
        """fast 역할 호출 테스트."""
        fast_response = {**OPENAI_SUCCESS_RESPONSE, "model": _FAST_MODEL}
        route = respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(200, json=fast_response)
        )

        result = await provider.invoke("fast", SAMPLE_MESSAGES)

        request = route.calls[0].request
        body = json.loads(request.content)
        assert body["model"] == _FAST_MODEL
        assert result["model"] == _FAST_MODEL

    @pytest.mark.asyncio
    async def test_invoke_invalid_role(self, provider: GatewayLLMProvider):
        """존재하지 않는 역할 호출 시 ValueError 테스트."""
        with pytest.raises(ValueError, match="역할 'nonexistent'에 매핑된 모델이 없습니다"):
            await provider.invoke("nonexistent", SAMPLE_MESSAGES)


# --- GatewayLLMProvider 에러 응답 테스트 ---


class TestGatewayErrors:
    """GatewayLLMProvider 에러 응답 테스트."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_http_401_error(self, provider: GatewayLLMProvider):
        """401 Unauthorized 에러 테스트."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await provider.invoke("primary", SAMPLE_MESSAGES)

        assert exc_info.value.response.status_code == 401

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_http_429_error(self, provider: GatewayLLMProvider):
        """429 Rate Limit 에러 테스트."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(429, json={"error": "Rate limit exceeded"})
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await provider.invoke("primary", SAMPLE_MESSAGES)

        assert exc_info.value.response.status_code == 429

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_http_500_error(self, provider: GatewayLLMProvider):
        """500 Internal Server Error 테스트."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(500, json={"error": "Internal Server Error"})
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await provider.invoke("primary", SAMPLE_MESSAGES)

        assert exc_info.value.response.status_code == 500


# --- GatewayLLMProvider 타임아웃 테스트 ---


class TestGatewayTimeout:
    """GatewayLLMProvider 타임아웃 테스트."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_timeout(self, provider: GatewayLLMProvider):
        """요청 타임아웃 테스트."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            side_effect=httpx.ReadTimeout("Connection timed out")
        )

        with pytest.raises(httpx.ReadTimeout):
            await provider.invoke("primary", SAMPLE_MESSAGES)

    @respx.mock
    @pytest.mark.asyncio
    async def test_invoke_connect_timeout(self, provider: GatewayLLMProvider):
        """연결 타임아웃 테스트."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            side_effect=httpx.ConnectTimeout("Connect timed out")
        )

        with pytest.raises(httpx.ConnectTimeout):
            await provider.invoke("primary", SAMPLE_MESSAGES)


# --- invoke_with_failover() 테스트 ---


class TestGatewayInvokeWithFailover:
    """invoke_with_failover() Failover 체인 테스트."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_success_on_primary_no_failover(
        self, provider: GatewayLLMProvider
    ):
        """주 역할 성공 시 failover 없이 즉시 반환."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(200, json=OPENAI_SUCCESS_RESPONSE)
        )

        result = await provider.invoke_with_failover("primary", SAMPLE_MESSAGES)

        assert result["id"] == "chatcmpl-test123"
        assert respx.calls.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_failover_primary_to_fast(
        self, provider: GatewayLLMProvider
    ):
        """primary 실패 → fast 성공 failover 테스트."""
        fast_response = {**OPENAI_SUCCESS_RESPONSE, "model": _FAST_MODEL}
        route = respx.post(CHAT_COMPLETIONS_URL).mock(
            side_effect=[
                httpx.Response(500, json={"error": "Server Error"}),
                httpx.Response(200, json=fast_response),
            ]
        )

        result = await provider.invoke_with_failover("primary", SAMPLE_MESSAGES)

        assert result["model"] == _FAST_MODEL
        assert route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_failover_reasoning_chain(
        self, provider: GatewayLLMProvider
    ):
        """reasoning → primary → fast 전체 체인 순회 테스트."""
        fast_response = {**OPENAI_SUCCESS_RESPONSE, "model": _FAST_MODEL}
        route = respx.post(CHAT_COMPLETIONS_URL).mock(
            side_effect=[
                httpx.Response(500, json={"error": "Error"}),   # reasoning 실패
                httpx.Response(500, json={"error": "Error"}),   # primary 실패
                httpx.Response(200, json=fast_response),         # fast 성공
            ]
        )

        result = await provider.invoke_with_failover("reasoning", SAMPLE_MESSAGES)

        assert result["model"] == _FAST_MODEL
        assert route.call_count == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_chain_exhausted_raises_runtime_error(
        self, provider: GatewayLLMProvider
    ):
        """모든 체인 소진 시 LLMProviderError 발생."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(500, json={"error": "Error"})
        )

        with pytest.raises(LLMProviderError, match="AI 서비스를 이용할 수 없습니다"):
            await provider.invoke_with_failover("primary", SAMPLE_MESSAGES)

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_triggers_failover(
        self, provider: GatewayLLMProvider
    ):
        """타임아웃 시 failover 전환."""
        fast_response = {**OPENAI_SUCCESS_RESPONSE, "model": _FAST_MODEL}
        respx.post(CHAT_COMPLETIONS_URL).mock(
            side_effect=[
                httpx.ReadTimeout("Timed out"),
                httpx.Response(200, json=fast_response),
            ]
        )

        result = await provider.invoke_with_failover("primary", SAMPLE_MESSAGES)

        assert result["model"] == _FAST_MODEL

    @respx.mock
    @pytest.mark.asyncio
    async def test_connect_error_triggers_failover(
        self, provider: GatewayLLMProvider
    ):
        """연결 실패 시 failover 전환."""
        fast_response = {**OPENAI_SUCCESS_RESPONSE, "model": _FAST_MODEL}
        respx.post(CHAT_COMPLETIONS_URL).mock(
            side_effect=[
                httpx.ConnectError("Connection refused"),
                httpx.Response(200, json=fast_response),
            ]
        )

        result = await provider.invoke_with_failover("primary", SAMPLE_MESSAGES)

        assert result["model"] == _FAST_MODEL

    @respx.mock
    @pytest.mark.asyncio
    async def test_max_retries_per_role(
        self, provider: GatewayLLMProvider
    ):
        """각 역할당 max_retries만큼 재시도 테스트."""
        fast_response = {**OPENAI_SUCCESS_RESPONSE, "model": _FAST_MODEL}
        route = respx.post(CHAT_COMPLETIONS_URL).mock(
            side_effect=[
                httpx.Response(500, json={"error": "Error"}),   # primary 시도 1
                httpx.Response(500, json={"error": "Error"}),   # primary 시도 2
                httpx.Response(200, json=fast_response),         # fast 시도 1
            ]
        )

        result = await provider.invoke_with_failover(
            "primary", SAMPLE_MESSAGES, max_retries=2
        )

        assert result["model"] == _FAST_MODEL
        assert route.call_count == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_chain_exhausted_with_retries_raises(
        self, provider: GatewayLLMProvider
    ):
        """max_retries 포함 전체 체인 소진 시 LLMProviderError."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(500, json={"error": "Error"})
        )

        with pytest.raises(LLMProviderError, match="AI 서비스를 이용할 수 없습니다"):
            await provider.invoke_with_failover(
                "primary", SAMPLE_MESSAGES, max_retries=2
            )

        # primary 2회 + fast 2회 = 4회
        assert respx.calls.call_count == 4

    @pytest.mark.asyncio
    async def test_empty_chain_raises_value_error(
        self, provider: GatewayLLMProvider
    ):
        """존재하지 않는 역할의 빈 체인 시 ValueError."""
        with pytest.raises(ValueError, match="fallback 체인이 비어 있습니다"):
            await provider.invoke_with_failover("nonexistent", SAMPLE_MESSAGES)

    @respx.mock
    @pytest.mark.asyncio
    async def test_accepts_trace_metadata(
        self, provider: GatewayLLMProvider
    ):
        """trace_metadata 파라미터 수용 테스트."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(200, json=OPENAI_SUCCESS_RESPONSE)
        )

        result = await provider.invoke_with_failover(
            "primary",
            SAMPLE_MESSAGES,
            max_retries=3,
            trace_metadata={"request_id": "test-123"},
        )

        assert result["id"] == "chatcmpl-test123"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fast_role_no_fallback(
        self, provider: GatewayLLMProvider
    ):
        """fast 역할 실패 시 fallback_role=null이므로 즉시 소진."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(500, json={"error": "Error"})
        )

        with pytest.raises(LLMProviderError, match="AI 서비스를 이용할 수 없습니다"):
            await provider.invoke_with_failover("fast", SAMPLE_MESSAGES)

        # fast만 1회
        assert respx.calls.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_4xx_not_retried(
        self, provider: GatewayLLMProvider
    ):
        """401 등 4xx(429 제외)는 failover 없이 즉시 전파."""
        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await provider.invoke_with_failover("primary", SAMPLE_MESSAGES)

        assert exc_info.value.response.status_code == 401
        # failover 시도 없이 1회만 호출
        assert respx.calls.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_429_triggers_failover(
        self, provider: GatewayLLMProvider
    ):
        """429 Rate Limit은 failover 대상."""
        fast_response = {**OPENAI_SUCCESS_RESPONSE, "model": _FAST_MODEL}
        route = respx.post(CHAT_COMPLETIONS_URL).mock(
            side_effect=[
                httpx.Response(429, json={"error": "Rate limit"}),
                httpx.Response(200, json=fast_response),
            ]
        )

        result = await provider.invoke_with_failover("primary", SAMPLE_MESSAGES)

        assert result["model"] == _FAST_MODEL
        assert route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_langfuse_span_created_on_success(
        self, provider: GatewayLLMProvider, monkeypatch,
    ):
        """성공 시 Langfuse Span이 생성되고 end()가 호출되는지 검증."""
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        mock_create_span = MagicMock(return_value=mock_span)
        monkeypatch.setattr(
            "src.providers.gateway.create_span", mock_create_span,
        )

        respx.post(CHAT_COMPLETIONS_URL).mock(
            return_value=httpx.Response(200, json=OPENAI_SUCCESS_RESPONSE)
        )

        await provider.invoke_with_failover("primary", SAMPLE_MESSAGES)

        mock_create_span.assert_called_once()
        call_kwargs = mock_create_span.call_args
        assert call_kwargs[1]["name"] == "llm-invoke:primary"
        assert call_kwargs[1]["input_data"]["role"] == "primary"
        assert call_kwargs[1]["input_data"]["is_fallback"] is False
        mock_span.update.assert_called_once()
        mock_span.end.assert_called_once()

    @respx.mock
    @pytest.mark.asyncio
    async def test_langfuse_span_records_failover_error(
        self, provider: GatewayLLMProvider, monkeypatch,
    ):
        """Failover 시 각 시도마다 Span에 에러가 기록되는지 검증."""
        from unittest.mock import MagicMock, call

        mock_spans = [MagicMock(), MagicMock()]
        mock_create_span = MagicMock(side_effect=mock_spans)
        monkeypatch.setattr(
            "src.providers.gateway.create_span", mock_create_span,
        )

        fast_response = {**OPENAI_SUCCESS_RESPONSE, "model": _FAST_MODEL}
        respx.post(CHAT_COMPLETIONS_URL).mock(
            side_effect=[
                httpx.Response(500, json={"error": "Server Error"}),
                httpx.Response(200, json=fast_response),
            ]
        )

        await provider.invoke_with_failover("primary", SAMPLE_MESSAGES)

        assert mock_create_span.call_count == 2
        # 첫 번째 span: primary 실패 → level="ERROR"
        error_update = mock_spans[0].update.call_args
        assert error_update[1]["level"] == "ERROR"
        assert error_update[1]["output"]["status"] == "error"
        mock_spans[0].end.assert_called_once()
        # 두 번째 span: fast 성공 → output은 LLM 응답 content
        success_update = mock_spans[1].update.call_args
        assert success_update[1]["output"] == "Hello! How can I help you?"
        mock_spans[1].end.assert_called_once()


# --- close() 테스트 ---


class TestGatewayClose:
    """GatewayLLMProvider close() 테스트."""

    @pytest.mark.asyncio
    async def test_close_after_use(self):
        """사용 후 close()가 클라이언트를 정리하는지 테스트."""
        p = GatewayLLMProvider(
            gateway_url=GATEWAY_URL,
            api_key=API_KEY,
            max_tokens=512,
            temperature=0.4,
            default_timeout=30.0,
        )
        # 클라이언트 생성 트리거
        client = p._ensure_client()
        assert not client.is_closed
        await p.close()
        assert client.is_closed

    @pytest.mark.asyncio
    async def test_close_without_use(self):
        """사용 전 close() 호출 시 에러 없음 테스트."""
        p = GatewayLLMProvider(
            gateway_url=GATEWAY_URL,
            api_key=API_KEY,
            max_tokens=512,
            temperature=0.4,
            default_timeout=30.0,
        )
        await p.close()  # 에러 없어야 함

    @pytest.mark.asyncio
    async def test_client_lazy_initialization(self):
        """클라이언트가 lazy 초기화되는지 테스트."""
        p = GatewayLLMProvider(
            gateway_url=GATEWAY_URL,
            api_key=API_KEY,
            max_tokens=512,
            temperature=0.4,
            default_timeout=30.0,
        )
        assert p._client is None
        client = p._ensure_client()
        assert client is not None
        assert p._client is client
        await p.close()


# --- DI(의존성 주입) 테스트 ---


class TestProviderDI:
    """Provider 의존성 주입 테스트."""

    def test_create_gateway_provider(self):
        """create_gateway_provider 팩토리 함수 테스트."""
        provider = create_gateway_provider()
        assert isinstance(provider, GatewayLLMProvider)
        assert isinstance(provider, BaseLLMProvider)

    def test_get_llm_provider_returns_singleton(self):
        """get_llm_provider 싱글턴 테스트."""
        from src.providers.deps import get_llm_provider

        get_llm_provider.cache_clear()
        provider1 = get_llm_provider()
        provider2 = get_llm_provider()
        assert provider1 is provider2
        get_llm_provider.cache_clear()

    def test_get_llm_provider_returns_base_type(self):
        """get_llm_provider 반환 타입 테스트."""
        from src.providers.deps import get_llm_provider

        get_llm_provider.cache_clear()
        provider = get_llm_provider()
        assert isinstance(provider, BaseLLMProvider)
        get_llm_provider.cache_clear()
