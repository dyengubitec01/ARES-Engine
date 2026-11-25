"""글로벌 예외 처리 및 에러 응답 테스트."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.responses import RAGCode
from app.core.exceptions import (
    BadRequestException,
    EmbeddingException,
    InternalServerException,
    RAGBaseException,
    RerankerException,
    VectorStoreException,
)
from app.main import create_app


# === 예외 클래스 테스트 ===


class TestExceptionClasses:
    """커스텀 예외 클래스 테스트."""

    def test_rag_base_exception_defaults(self):
        """RAGBaseException 기본값 확인."""
        exc = RAGBaseException()
        assert exc.code == RAGCode.INTERNAL_ERROR
        assert exc.msg == "서버 내부 오류"
        assert exc.status_code == 500

    def test_bad_request_exception(self):
        """BadRequestException 코드 및 상태 확인."""
        exc = BadRequestException()
        assert exc.code == RAGCode.BAD_REQUEST
        assert exc.status_code == 400
        assert exc.msg == "잘못된 요청"

    def test_bad_request_custom_msg(self):
        """BadRequestException 커스텀 메시지 확인."""
        exc = BadRequestException(msg="쿼리 누락")
        assert exc.msg == "쿼리 누락"

    def test_reranker_exception(self):
        """RerankerException 코드 및 상태 확인."""
        exc = RerankerException()
        assert exc.code == RAGCode.RERANKER_FAILURE
        assert exc.status_code == 502

    def test_embedding_exception(self):
        """EmbeddingException 코드 및 상태 확인."""
        exc = EmbeddingException()
        assert exc.code == RAGCode.EMBEDDING_FAILURE
        assert exc.status_code == 502
        assert exc.msg == "임베딩 연동 실패"

    def test_vector_store_exception(self):
        """VectorStoreException 코드 및 상태 확인."""
        exc = VectorStoreException()
        assert exc.code == RAGCode.VECTOR_STORE_FAILURE
        assert exc.status_code == 502
        assert exc.msg == "벡터 스토어 연동 실패"

    def test_internal_server_exception(self):
        """InternalServerException 코드 및 상태 확인."""
        exc = InternalServerException()
        assert exc.code == RAGCode.INTERNAL_ERROR
        assert exc.status_code == 500

    def test_inheritance(self):
        """모든 예외가 RAGBaseException을 상속하는지 확인."""
        assert issubclass(BadRequestException, RAGBaseException)
        assert issubclass(EmbeddingException, RAGBaseException)
        assert issubclass(RerankerException, RAGBaseException)
        assert issubclass(VectorStoreException, RAGBaseException)
        assert issubclass(InternalServerException, RAGBaseException)


# === ExceptionHandler 통합 테스트 ===


class TestExceptionHandlers:
    """글로벌 ExceptionHandler 통합 테스트."""

    async def test_validation_error_returns_rag100020(self, app):
        """query 누락 시 RAG100020 표준 에러 응답 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/search", json={})
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "RAG100020"
        assert "data" not in data

    async def test_empty_query_returns_rag100020(self, app):
        """빈 query 문자열 시 RAG100020 응답 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "   ", "user_depts": ["test-dept"]}
            )
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "RAG100020"

    async def test_negative_top_k_returns_rag100020(self, app):
        """음수 top_k 시 RAG100020 응답 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "test", "user_depts": ["test-dept"], "top_k": -1}
            )
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "RAG100020"

    async def test_http_exception_returns_standard_format(self, app):
        """존재하지 않는 경로 요청 시 표준 에러 응답 형식 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert data["code"] == "RAG100020"
        assert "msg" in data

    async def test_method_not_allowed_returns_standard_format(self, app):
        """잘못된 HTTP 메서드 요청 시 표준 에러 응답 형식 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/search")
        assert response.status_code == 405
        data = response.json()
        assert data["code"] == "RAG100020"

    async def test_error_response_no_stack_trace(self, app):
        """에러 응답에 스택 트레이스가 포함되지 않는지 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/search", json={})
        body = response.text
        assert "Traceback" not in body
        assert "File" not in body

    async def test_normal_request_still_works(self, app):
        """예외 핸들러 등록 후에도 정상 요청이 작동하는지 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "정상 요청", "user_depts": ["test-dept"]}
            )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "RAG100000"
