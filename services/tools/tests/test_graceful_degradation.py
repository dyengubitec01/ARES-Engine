"""Graceful Degradation 테스트.

LLMProviderError 예외 및 전역 핸들러를 통한
TOL 표준 응답(TOL020130, HTTP 503) 변환 검증.
"""

import pytest
from fastapi.testclient import TestClient

from src.exceptions.exceptions import LLMProviderError
from src.main import app
from src.schemas.codes import TOLCode, TOLMessage


# --- 테스트용 임시 엔드포인트 등록 (모듈 레벨) ---


@pytest.fixture(scope="module", autouse=True)
def _register_test_routes():
    """테스트용 엔드포인트를 한 번만 등록하고 모듈 종료 시 정리."""

    @app.get("/test-degradation")
    async def trigger_degradation():
        raise LLMProviderError(
            detail="현재 AI 서비스를 이용할 수 없습니다.",
            role="primary",
            chain=["primary", "fast"],
        )

    yield
    app.routes[:] = [
        r for r in app.routes
        if not getattr(r, "path", "").startswith("/test-degradation")
    ]


# --- LLMProviderError 예외 테스트 ---


class TestLLMProviderError:
    """LLMProviderError 예외 클래스 테스트."""

    def test_basic_creation(self):
        """기본 생성 테스트."""
        exc = LLMProviderError(detail="서비스 이용 불가")
        assert exc.detail == "서비스 이용 불가"
        assert exc.role == ""
        assert exc.chain == []
        assert str(exc) == "서비스 이용 불가"

    def test_with_role_and_chain(self):
        """role, chain 포함 생성 테스트."""
        exc = LLMProviderError(
            detail="메시지",
            role="primary",
            chain=["primary", "fast"],
        )
        assert exc.role == "primary"
        assert exc.chain == ["primary", "fast"]

    def test_is_exception(self):
        """Exception 서브클래스 테스트."""
        exc = LLMProviderError(detail="test")
        assert isinstance(exc, Exception)


# --- 전역 예외 핸들러 테스트 ---


class TestGracefulDegradationHandler:
    """전역 예외 핸들러를 통한 TOL 표준 응답 변환 테스트."""

    def test_handler_returns_503_with_tol_response(self):
        """체인 소진 시 HTTP 503 + TOL 표준 응답 반환."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-degradation")

        assert response.status_code == 503
        body = response.json()
        assert body["code"] == TOLCode.ERROR_LLM_CONNECTION.value
        assert body["msg"] == TOLMessage.LLM_CONNECTION_FAILED.value

    def test_handler_response_data_is_null(self):
        """에러 응답의 data 필드가 null이어야 함."""
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/test-degradation")

        body = response.json()
        assert body["data"] is None
