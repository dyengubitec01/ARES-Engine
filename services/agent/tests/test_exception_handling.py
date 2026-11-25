"""Tests for Story 1.6: Exception Handling and Response Standardization."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.enums import ErrorCode
from app.core.exceptions import BusinessException
from app.core.handlers import register_exception_handlers
from app.core.schemas.response import CommonResponse


class TestErrorCode:
    """Tests for ErrorCode Enum (AC 1.6.1)."""

    def test_error_code_success_properties(self) -> None:
        """Test SUCCESS error code properties."""
        assert ErrorCode.SUCCESS.code == "AGT0000"
        assert ErrorCode.SUCCESS.msg == "요청이 성공하였습니다."
        assert ErrorCode.SUCCESS.http_status == 200

    def test_error_code_validation_error_properties(self) -> None:
        """Test VALIDATION_ERROR code properties."""
        assert ErrorCode.VALIDATION_ERROR.code == "AGT4000"
        assert ErrorCode.VALIDATION_ERROR.msg == "입력값이 유효하지 않습니다."
        assert ErrorCode.VALIDATION_ERROR.http_status == 400

    def test_error_code_invalid_request_properties(self) -> None:
        """Test INVALID_REQUEST code properties."""
        assert ErrorCode.INVALID_REQUEST.code == "AGT4001"
        assert ErrorCode.INVALID_REQUEST.msg == "잘못된 요청입니다."
        assert ErrorCode.INVALID_REQUEST.http_status == 400

    def test_error_code_internal_error_properties(self) -> None:
        """Test INTERNAL_ERROR code properties."""
        assert ErrorCode.INTERNAL_ERROR.code == "AGT5000"
        assert ErrorCode.INTERNAL_ERROR.msg == "내부 서버 오류가 발생했습니다."
        assert ErrorCode.INTERNAL_ERROR.http_status == 500

    def test_error_code_llm_connection_properties(self) -> None:
        """Test LLM_CONNECTION code properties."""
        assert ErrorCode.LLM_CONNECTION.code == "AGT5001"
        assert ErrorCode.LLM_CONNECTION.msg == "LLM 서버에 연결할 수 없습니다."
        assert ErrorCode.LLM_CONNECTION.http_status == 503

    def test_error_code_llm_response_properties(self) -> None:
        """Test LLM_RESPONSE code properties."""
        assert ErrorCode.LLM_RESPONSE.code == "AGT5002"
        assert ErrorCode.LLM_RESPONSE.msg == "LLM 응답 처리 중 오류가 발생했습니다."
        assert ErrorCode.LLM_RESPONSE.http_status == 502

    def test_error_code_rag_search_properties(self) -> None:
        """Test RAG_SEARCH code properties."""
        assert ErrorCode.RAG_SEARCH.code == "AGT5003"
        assert ErrorCode.RAG_SEARCH.http_status == 503

    def test_error_code_tool_execution_properties(self) -> None:
        """Test TOOL_EXECUTION code properties."""
        assert ErrorCode.TOOL_EXECUTION.code == "AGT5004"
        assert ErrorCode.TOOL_EXECUTION.http_status == 503

    def test_error_code_all_servers_down_properties(self) -> None:
        """Test ALL_SERVERS_DOWN code properties."""
        assert ErrorCode.ALL_SERVERS_DOWN.code == "AGT5010"
        assert ErrorCode.ALL_SERVERS_DOWN.msg == "일시적으로 서비스를 이용할 수 없습니다."
        assert ErrorCode.ALL_SERVERS_DOWN.http_status == 503

    def test_all_error_codes_have_properties(self) -> None:
        """Test all ErrorCode members have required properties."""
        for error_code in ErrorCode:
            assert isinstance(error_code.code, str)
            assert error_code.code.startswith("AGT")
            assert isinstance(error_code.msg, str)
            assert len(error_code.msg) > 0
            assert isinstance(error_code.http_status, int)
            assert 200 <= error_code.http_status < 600


class TestBusinessException:
    """Tests for BusinessException class (AC 1.6.2)."""

    def test_basic_exception(self) -> None:
        """Test basic BusinessException creation."""
        exc = BusinessException(ErrorCode.VALIDATION_ERROR)

        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.code == "AGT4000"
        assert exc.msg == "입력값이 유효하지 않습니다."
        assert exc.http_status == 400
        assert exc.detail is None

    def test_exception_with_detail(self) -> None:
        """Test BusinessException with detail message."""
        exc = BusinessException(ErrorCode.LLM_CONNECTION, detail="primary 서버 타임아웃")

        assert exc.error_code == ErrorCode.LLM_CONNECTION
        assert exc.code == "AGT5001"
        assert exc.detail == "primary 서버 타임아웃"
        assert exc.msg == "LLM 서버에 연결할 수 없습니다.: primary 서버 타임아웃"
        assert exc.http_status == 503

    def test_exception_inherits_from_exception(self) -> None:
        """Test BusinessException inherits from Exception."""
        exc = BusinessException(ErrorCode.INTERNAL_ERROR)

        assert isinstance(exc, Exception)
        assert str(exc) == "내부 서버 오류가 발생했습니다."

    def test_exception_can_be_raised_and_caught(self) -> None:
        """Test BusinessException can be raised and caught."""
        with pytest.raises(BusinessException) as exc_info:
            raise BusinessException(ErrorCode.ALL_SERVERS_DOWN, detail="테스트")

        assert exc_info.value.error_code == ErrorCode.ALL_SERVERS_DOWN
        assert exc_info.value.detail == "테스트"


class TestCommonResponse:
    """Tests for CommonResponse class (AC 1.6.3)."""

    def test_success_response_default(self) -> None:
        """Test CommonResponse.success() with default values."""
        response = CommonResponse.success()

        assert response.code == "AGT0000"
        assert response.msg == "요청이 성공하였습니다."
        assert response.data is None

    def test_success_response_with_data(self) -> None:
        """Test CommonResponse.success() with data."""
        data = {"id": 1, "name": "test"}
        response = CommonResponse.success(data=data)

        assert response.code == "AGT0000"
        assert response.msg == "요청이 성공하였습니다."
        assert response.data == data

    def test_success_response_custom_error_code(self) -> None:
        """Test CommonResponse.success() with custom ErrorCode."""
        response = CommonResponse.success(
            data={"status": "ok"},
            error_code=ErrorCode.SUCCESS,
        )

        assert response.code == "AGT0000"
        assert response.data == {"status": "ok"}

    def test_error_response_basic(self) -> None:
        """Test CommonResponse.error() basic usage."""
        response = CommonResponse.error(ErrorCode.VALIDATION_ERROR)

        assert response.code == "AGT4000"
        assert response.msg == "입력값이 유효하지 않습니다."
        assert response.data is None

    def test_error_response_with_detail(self) -> None:
        """Test CommonResponse.error() with detail."""
        response = CommonResponse.error(
            ErrorCode.LLM_CONNECTION,
            detail="서버 응답 없음",
        )

        assert response.code == "AGT5001"
        assert response.msg == "LLM 서버에 연결할 수 없습니다.: 서버 응답 없음"
        assert response.data is None

    def test_response_serialization(self) -> None:
        """Test CommonResponse JSON serialization."""
        response = CommonResponse.success(data={"test": True})
        serialized = response.model_dump()

        assert serialized == {
            "code": "AGT0000",
            "msg": "요청이 성공하였습니다.",
            "data": {"test": True},
        }

    def test_error_response_serialization(self) -> None:
        """Test CommonResponse.error() JSON serialization."""
        response = CommonResponse.error(ErrorCode.INTERNAL_ERROR)
        serialized = response.model_dump()

        assert serialized == {
            "code": "AGT5000",
            "msg": "내부 서버 오류가 발생했습니다.",
            "data": None,
        }


class TestExceptionHandlers:
    """Tests for global exception handlers (AC 1.6.4, 1.6.6, 1.6.7)."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test FastAPI app with handlers."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test-business-exception")
        async def raise_business_exception():
            raise BusinessException(ErrorCode.VALIDATION_ERROR, detail="필드 누락")

        @app.get("/test-llm-error")
        async def raise_llm_error():
            raise BusinessException(ErrorCode.LLM_CONNECTION)

        @app.get("/test-unhandled")
        async def raise_unhandled():
            raise RuntimeError("Unexpected error")

        class TestInput(BaseModel):
            name: str
            age: int

        @app.post("/test-validation")
        async def validate_input(data: TestInput):
            return {"received": data.model_dump()}

        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create test client with raise_server_exceptions=False for 500 tests."""
        return TestClient(app, raise_server_exceptions=False)

    def test_business_exception_handler_validation_error(
        self, client: TestClient
    ) -> None:
        """Test BusinessException handler with VALIDATION_ERROR."""
        response = client.get("/test-business-exception")

        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "AGT4000"
        assert "입력값이 유효하지 않습니다." in data["msg"]
        assert "필드 누락" in data["msg"]
        assert "data" not in data  # Story 2.7: data 필드 제거

    def test_business_exception_handler_llm_error(self, client: TestClient) -> None:
        """Test BusinessException handler with LLM_CONNECTION (503)."""
        response = client.get("/test-llm-error")

        assert response.status_code == 503
        data = response.json()
        assert data["code"] == "AGT5001"
        assert data["msg"] == "LLM 서버에 연결할 수 없습니다."

    def test_unhandled_exception_handler(self, client: TestClient) -> None:
        """Test unhandled Exception handler (AC 1.6.6)."""
        response = client.get("/test-unhandled")

        assert response.status_code == 500
        data = response.json()
        assert data["code"] == "AGT5000"
        assert data["msg"] == "내부 서버 오류가 발생했습니다."
        assert "data" not in data  # Story 2.7: data 필드 제거
        # Error detail should NOT be exposed to client

    def test_request_validation_error_handler(self, client: TestClient) -> None:
        """Test RequestValidationError handler (AC 2.7.7)."""
        response = client.post(
            "/test-validation",
            json={"invalid": "data"},  # Missing required fields
        )

        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "AGT4000"
        assert data["msg"] == "입력값이 유효하지 않습니다."
        assert "data" not in data  # Story 2.7: data 필드 제거

    def test_request_validation_error_type_mismatch(self, client: TestClient) -> None:
        """Test RequestValidationError with type mismatch."""
        response = client.post(
            "/test-validation",
            json={"name": "test", "age": "not-a-number"},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "AGT4000"
        assert "data" not in data  # Story 2.7: data 필드 제거


class TestExceptionHandlerHttpStatus:
    """Tests for dynamic HTTP status codes (AC 1.6.4)."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create test FastAPI app."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/error/{error_type}")
        async def raise_error(error_type: str):
            error_map = {
                "validation": ErrorCode.VALIDATION_ERROR,
                "invalid_request": ErrorCode.INVALID_REQUEST,
                "internal": ErrorCode.INTERNAL_ERROR,
                "llm_connection": ErrorCode.LLM_CONNECTION,
                "llm_response": ErrorCode.LLM_RESPONSE,
                "rag_search": ErrorCode.RAG_SEARCH,
                "tool_execution": ErrorCode.TOOL_EXECUTION,
                "all_servers_down": ErrorCode.ALL_SERVERS_DOWN,
            }
            if error_type in error_map:
                raise BusinessException(error_map[error_type])
            return {"error_type": error_type}

        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_http_status_400_validation(self, client: TestClient) -> None:
        """Test 400 status for VALIDATION_ERROR."""
        response = client.get("/error/validation")
        assert response.status_code == 400

    def test_http_status_400_invalid_request(self, client: TestClient) -> None:
        """Test 400 status for INVALID_REQUEST."""
        response = client.get("/error/invalid_request")
        assert response.status_code == 400

    def test_http_status_500_internal(self, client: TestClient) -> None:
        """Test 500 status for INTERNAL_ERROR."""
        response = client.get("/error/internal")
        assert response.status_code == 500

    def test_http_status_503_llm_connection(self, client: TestClient) -> None:
        """Test 503 status for LLM_CONNECTION."""
        response = client.get("/error/llm_connection")
        assert response.status_code == 503

    def test_http_status_502_llm_response(self, client: TestClient) -> None:
        """Test 502 status for LLM_RESPONSE."""
        response = client.get("/error/llm_response")
        assert response.status_code == 502

    def test_http_status_503_rag_search(self, client: TestClient) -> None:
        """Test 503 status for RAG_SEARCH."""
        response = client.get("/error/rag_search")
        assert response.status_code == 503

    def test_http_status_503_tool_execution(self, client: TestClient) -> None:
        """Test 503 status for TOOL_EXECUTION."""
        response = client.get("/error/tool_execution")
        assert response.status_code == 503

    def test_http_status_503_all_servers_down(self, client: TestClient) -> None:
        """Test 503 status for ALL_SERVERS_DOWN."""
        response = client.get("/error/all_servers_down")
        assert response.status_code == 503
