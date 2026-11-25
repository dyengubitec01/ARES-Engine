"""Health check 엔드포인트 테스트."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    """테스트용 FastAPI 앱 인스턴스."""
    return create_app()


@pytest.mark.asyncio
async def test_health_returns_200(app):
    """/health 엔드포인트가 200 OK를 반환하는지 확인."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_response_body(app):
    """/health 응답에 status와 env 필드가 포함되는지 확인."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "env" in data


@pytest.mark.asyncio
async def test_health_env_matches_settings(app):
    """/health 응답의 env가 Settings.APP_ENV와 일치하는지 확인."""
    from app.core.config import get_settings

    settings = get_settings()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    data = response.json()
    assert data["env"] == settings.APP_ENV
