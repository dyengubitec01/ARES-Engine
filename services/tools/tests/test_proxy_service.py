"""외부 API 프록시 Service 테스트.

Config 로더 + Proxy Service + 에러 처리 테스트.
"""

import httpx
import pytest
import respx

from src.config.proxy import (
    ProxyConfig,
    ProxyDefaults,
    ProxyTargetConfig,
    load_proxy_config,
)
from src.exceptions.exceptions import ExternalAPIError
from src.schemas.codes import TOLCode, TOLMessage
from src.services.proxy import get_proxy_target, proxy_request


# ── Config 로더 테스트 ──


@pytest.fixture(autouse=True)
def clear_proxy_cache():
    """각 테스트마다 프록시 설정 캐시 클리어."""
    load_proxy_config.cache_clear()
    yield
    load_proxy_config.cache_clear()


class TestProxyConfigLoader:
    """config/proxy.yaml 로더 테스트."""

    def test_load_returns_proxy_config(self):
        """로드 결과가 ProxyConfig 인스턴스."""
        config = load_proxy_config()
        assert isinstance(config, ProxyConfig)

    def test_defaults_loaded(self):
        """기본 설정(defaults) 로드."""
        config = load_proxy_config()
        assert isinstance(config.defaults, ProxyDefaults)
        assert config.defaults.timeout > 0
        assert config.defaults.max_retries >= 0

    def test_targets_loaded(self):
        """프록시 대상 목록 로드."""
        config = load_proxy_config()
        assert isinstance(config.targets, tuple)
        assert len(config.targets) > 0

    def test_target_has_required_fields(self):
        """각 대상이 필수 필드 보유."""
        config = load_proxy_config()
        for target in config.targets:
            assert isinstance(target, ProxyTargetConfig)
            assert target.name
            assert target.base_url
            assert target.timeout > 0

    def test_get_target_by_name(self):
        """이름으로 대상 조회."""
        config = load_proxy_config()
        first_name = config.targets[0].name
        target = config.get_target(first_name)
        assert target is not None
        assert target.name == first_name

    def test_get_target_nonexistent_returns_none(self):
        """존재하지 않는 이름 → None."""
        config = load_proxy_config()
        assert config.get_target("nonexistent-api") is None

    def test_get_target_names(self):
        """대상 이름 목록 조회."""
        config = load_proxy_config()
        names = config.get_target_names()
        assert isinstance(names, list)
        assert len(names) > 0

    def test_frozen_dataclass(self):
        """ProxyConfig는 frozen (불변)."""
        config = load_proxy_config()
        with pytest.raises(AttributeError):
            config.defaults = None  # type: ignore[misc]


# ── get_proxy_target 헬퍼 테스트 ──


class TestGetProxyTarget:
    """get_proxy_target 함수 테스트."""

    def test_valid_name_returns_target(self):
        """유효한 이름 → ProxyTargetConfig 반환."""
        config = load_proxy_config()
        first_name = config.targets[0].name
        target = get_proxy_target(first_name)
        assert target.name == first_name

    def test_invalid_name_raises_error(self):
        """등록되지 않은 이름 → ExternalAPIError."""
        with pytest.raises(ExternalAPIError) as exc_info:
            get_proxy_target("nonexistent-api")
        assert exc_info.value.api_name == "nonexistent-api"
        assert "등록되지 않은 프록시 대상" in exc_info.value.detail


# ── Proxy Service 테스트 ──


class TestProxyRequest:
    """proxy_request 함수 테스트."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_get_request(self):
        """GET 요청 성공."""
        config = load_proxy_config()
        target = config.targets[0]

        respx.get(target.base_url).mock(
            return_value=httpx.Response(
                200,
                json={"result": "ok"},
                headers={"content-type": "application/json"},
            )
        )

        result = await proxy_request(api_name=target.name)

        assert result["status_code"] == 200
        assert result["body"] == {"result": "ok"}

    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_post_request(self):
        """POST 요청 + body 전달 성공."""
        config = load_proxy_config()
        target = config.targets[0]

        respx.post(target.base_url).mock(
            return_value=httpx.Response(
                201,
                json={"created": True},
                headers={"content-type": "application/json"},
            )
        )

        result = await proxy_request(
            api_name=target.name,
            method="POST",
            body={"data": "test"},
        )

        assert result["status_code"] == 201

    @respx.mock
    @pytest.mark.asyncio
    async def test_path_appended_to_base_url(self):
        """path 파라미터가 base_url에 추가됨."""
        config = load_proxy_config()
        target = config.targets[0]
        expected_url = f"{target.base_url.rstrip('/')}/json"

        respx.get(expected_url).mock(
            return_value=httpx.Response(
                200,
                json={"ok": True},
                headers={"content-type": "application/json"},
            )
        )

        result = await proxy_request(api_name=target.name, path="json")

        assert result["status_code"] == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_4xx_error_no_retry(self):
        """4xx 에러 → 재시도 없이 즉시 ExternalAPIError."""
        config = load_proxy_config()
        target = config.targets[0]

        route = respx.get(target.base_url).mock(
            return_value=httpx.Response(400, text="Bad Request")
        )

        with pytest.raises(ExternalAPIError) as exc_info:
            await proxy_request(api_name=target.name)

        assert exc_info.value.status_code == 400
        assert route.call_count == 1  # 재시도 없음

    @respx.mock
    @pytest.mark.asyncio
    async def test_5xx_error_retries(self):
        """5xx 에러 → max_retries만큼 재시도 후 ExternalAPIError."""
        config = load_proxy_config()
        target = config.targets[0]

        route = respx.get(target.base_url).mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        with pytest.raises(ExternalAPIError) as exc_info:
            await proxy_request(api_name=target.name)

        assert exc_info.value.status_code == 500
        assert route.call_count == target.max_retries

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_retries(self):
        """타임아웃 → max_retries만큼 재시도 후 ExternalAPIError."""
        config = load_proxy_config()
        target = config.targets[0]

        route = respx.get(target.base_url).mock(
            side_effect=httpx.ReadTimeout("read timeout")
        )

        with pytest.raises(ExternalAPIError) as exc_info:
            await proxy_request(api_name=target.name)

        assert "타임아웃" in exc_info.value.detail
        assert route.call_count == target.max_retries

    @respx.mock
    @pytest.mark.asyncio
    async def test_connection_error_retries(self):
        """연결 실패 → max_retries만큼 재시도 후 ExternalAPIError."""
        config = load_proxy_config()
        target = config.targets[0]

        route = respx.get(target.base_url).mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        with pytest.raises(ExternalAPIError) as exc_info:
            await proxy_request(api_name=target.name)

        assert "연결 실패" in exc_info.value.detail
        assert route.call_count == target.max_retries

    @respx.mock
    @pytest.mark.asyncio
    async def test_nonexistent_api_raises_error(self):
        """등록되지 않은 API → ExternalAPIError."""
        with pytest.raises(ExternalAPIError) as exc_info:
            await proxy_request(api_name="no-such-api")

        assert exc_info.value.api_name == "no-such-api"

    @respx.mock
    @pytest.mark.asyncio
    async def test_text_response_body(self):
        """JSON이 아닌 응답 → body가 text."""
        config = load_proxy_config()
        target = config.targets[0]

        respx.get(target.base_url).mock(
            return_value=httpx.Response(
                200,
                text="plain text response",
                headers={"content-type": "text/plain"},
            )
        )

        result = await proxy_request(api_name=target.name)

        assert result["status_code"] == 200
        assert result["body"] == "plain text response"


# ── Langfuse Span 테스트 ──


class TestProxyRequestLangfuse:
    """proxy_request Langfuse Span 테스트."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_span_created_on_success(self, monkeypatch):
        """성공 시 Langfuse span 생성 및 종료."""
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        mock_create_span = MagicMock(return_value=mock_span)
        monkeypatch.setattr("src.services.proxy.create_span", mock_create_span)

        config = load_proxy_config()
        target = config.targets[0]

        respx.get(target.base_url).mock(
            return_value=httpx.Response(
                200,
                json={"ok": True},
                headers={"content-type": "application/json"},
            )
        )

        await proxy_request(api_name=target.name)

        mock_create_span.assert_called_once()
        call_kwargs = mock_create_span.call_args[1]
        assert call_kwargs["name"] == "proxy-request"
        assert call_kwargs["input_data"]["api_name"] == target.name
        mock_span.update.assert_called_once()
        assert mock_span.update.call_args[1]["output"]["status"] == "success"
        mock_span.end.assert_called_once()

    @respx.mock
    @pytest.mark.asyncio
    async def test_span_records_error_on_failure(self, monkeypatch):
        """실패 시 Langfuse span에 에러 기록."""
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        mock_create_span = MagicMock(return_value=mock_span)
        monkeypatch.setattr("src.services.proxy.create_span", mock_create_span)

        config = load_proxy_config()
        target = config.targets[0]

        respx.get(target.base_url).mock(
            return_value=httpx.Response(500, text="Server Error")
        )

        with pytest.raises(ExternalAPIError):
            await proxy_request(api_name=target.name)

        mock_span.update.assert_called_once()
        assert mock_span.update.call_args[1]["level"] == "ERROR"
        assert mock_span.update.call_args[1]["output"]["status"] == "failed"
        mock_span.end.assert_called_once()


# ── 예외 및 에러 코드 테스트 ──


class TestExternalAPIError:
    """ExternalAPIError 예외 테스트."""

    def test_exception_attributes(self):
        """예외 속성 정상."""
        exc = ExternalAPIError(
            api_name="test-api",
            status_code=500,
            detail="서버 에러",
        )
        assert exc.api_name == "test-api"
        assert exc.status_code == 500
        assert exc.detail == "서버 에러"

    def test_exception_string(self):
        """예외 문자열 표현."""
        exc = ExternalAPIError(api_name="test-api", detail="에러")
        assert "test-api" in str(exc)

    def test_error_code_exists(self):
        """TOL 에러 코드 존재."""
        assert TOLCode.ERROR_EXTERNAL_API.value == "TOL030130"

    def test_error_message_exists(self):
        """TOL 에러 메시지 존재."""
        assert TOLMessage.EXTERNAL_API_FAILED.value == "외부 API 호출 실패"


# ── 전역 핸들러 통합 테스트 ──


class TestExternalAPIErrorHandler:
    """ExternalAPIError 전역 핸들러 통합 테스트."""

    def test_handler_registered(self):
        """핸들러가 app에 등록됨."""
        from src.main import app

        handlers = app.exception_handlers
        assert ExternalAPIError in handlers

    def test_handler_returns_502_with_tol_response(self):
        """핸들러가 HTTP 502 + TOL030130 반환."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.exceptions.handlers import register_exception_handlers

        test_app = FastAPI()
        register_exception_handlers(test_app)

        @test_app.get("/trigger")
        async def trigger():
            raise ExternalAPIError(
                api_name="test-api", status_code=500, detail="서버 에러",
            )

        client = TestClient(test_app)
        resp = client.get("/trigger")
        assert resp.status_code == 502
        data = resp.json()
        assert data["code"] == TOLCode.ERROR_EXTERNAL_API.value
        assert data["msg"] == TOLMessage.EXTERNAL_API_FAILED.value
        assert data["data"] is None
