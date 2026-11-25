"""검색 파이프라인 통합 테스트 — 실서버 연동.

실행 조건: pytest --run-integration
필요 서비스: 임베딩 API (EMBEDDING_API_URL), Qdrant (QDRANT_URL)
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def prod_app():
    """APP_ENV=prod로 생성한 FastAPI 앱 인스턴스."""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"APP_ENV": "prod"}, clear=False):
        get_settings.cache_clear()
        app = create_app()
    yield app
    get_settings.cache_clear()


@pytest.mark.integration
class TestSearchPipelineIntegration:
    """query → embed → vector search → rerank 파이프라인 통합 테스트."""

    async def test_full_pipeline_returns_success(self, prod_app):
        """정상 쿼리가 RAG100000 성공 응답을 반환하는지 확인."""
        transport = ASGITransport(app=prod_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "통합 테스트 쿼리", "user_depts": ["f5542890-753b-47f8-9dc8-9591cc4aa8ca"]}
            )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "RAG100000"
        assert "data" in data

    async def test_pipeline_response_structure(self, prod_app):
        """응답 data에 query, trace_id, results가 포함되는지 확인."""
        transport = ASGITransport(app=prod_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "파이프라인 구조 테스트", "user_depts": ["f5542890-753b-47f8-9dc8-9591cc4aa8ca"]}
            )
        result_data = response.json()["data"]
        assert result_data["query"] == "파이프라인 구조 테스트"
        assert "trace_id" in result_data
        assert isinstance(result_data["results"], list)

    async def test_pipeline_with_custom_top_k(self, prod_app):
        """top_k 파라미터가 결과 수를 제한하는지 확인."""
        transport = ASGITransport(app=prod_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search",
                json={"query": "top_k 통합 테스트", "user_depts": ["f5542890-753b-47f8-9dc8-9591cc4aa8ca"], "top_k": 2, "search_k": 10},
            )
        assert response.status_code == 200
        results = response.json()["data"]["results"]
        assert len(results) <= 2
