"""catch-all 예외 핸들러 테스트.

예상치 못한 예외 발생 시 FastAPI 기본 500 대신
TOL 표준 응답(TOL000030)으로 반환되는지 검증한다.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.schemas.codes import TOLCode, TOLMessage


@pytest.fixture
def unhandled_route():
    """테스트용 엔드포인트 — 의도적 예외 발생."""

    @app.get("/test/unhandled-error")
    async def _raise():
        raise RuntimeError("의도적 테스트 예외")

    yield
    # cleanup: 테스트 후 라우트 제거
    app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != "/test/unhandled-error"]


@pytest.mark.asyncio
async def test_unhandled_exception_returns_tol_standard_response(unhandled_route):
    """예상치 못한 예외 → TOL 표준 500 응답."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test/unhandled-error")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == TOLCode.ERROR_INTERNAL.value
    assert body["msg"] == TOLMessage.INTERNAL_ERROR.value


@pytest.mark.asyncio
async def test_unhandled_exception_does_not_expose_stacktrace(unhandled_route):
    """500 응답에 스택트레이스나 내부 정보가 노출되지 않는지 확인."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test/unhandled-error")

    body = response.json()
    assert "traceback" not in str(body).lower()
    assert "RuntimeError" not in body.get("msg", "")
    assert body.get("data") is None
