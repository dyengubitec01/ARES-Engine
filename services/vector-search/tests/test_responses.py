"""표준 응답 규격 및 커스텀 코드 테스트."""

import pytest

from app.api.responses import (
    APIResponse,
    RAGCode,
    error_response,
    no_result_response,
    success_response,
)


class TestRAGCode:
    """RAGCode Enum 테스트."""

    def test_code_format_9_chars(self):
        """모든 코드가 9자리 문자열(RAG + 6자리)인지 확인."""
        for code in RAGCode:
            assert len(code.value) == 9
            assert code.value.startswith("RAG")
            assert code.value[3:].isdigit()

    def test_defined_codes(self):
        """정의된 코드가 존재하는지 확인."""
        assert RAGCode.SEARCH_SUCCESS.value == "RAG100000"
        assert RAGCode.NO_RESULT.value == "RAG100001"
        assert RAGCode.BAD_REQUEST.value == "RAG100020"
        assert RAGCode.EMBEDDING_FAILURE.value == "RAG100040"
        assert RAGCode.RERANKER_FAILURE.value == "RAG100050"
        assert RAGCode.VECTOR_STORE_FAILURE.value == "RAG100060"
        assert RAGCode.INTERNAL_ERROR.value == "RAG100099"

    def test_default_messages(self):
        """각 코드의 기본 메시지가 존재하는지 확인."""
        for code in RAGCode:
            assert isinstance(code.default_message, str)
            assert len(code.default_message) > 0

    def test_specific_default_messages(self):
        """PRD에 정의된 기본 메시지 확인."""
        assert RAGCode.SEARCH_SUCCESS.default_message == "검색 성공"
        assert RAGCode.NO_RESULT.default_message == "검색 결과 없음"
        assert RAGCode.BAD_REQUEST.default_message == "잘못된 요청"
        assert RAGCode.RERANKER_FAILURE.default_message == "리랭커 연동 실패"
        assert RAGCode.INTERNAL_ERROR.default_message == "서버 내부 오류"


class TestAPIResponse:
    """APIResponse 모델 테스트."""

    def test_with_data(self):
        """data가 있을 때 to_dict에 포함되는지 확인."""
        resp = APIResponse(code="RAG100000", msg="검색 성공", data={"key": "value"})
        d = resp.to_dict()
        assert d["code"] == "RAG100000"
        assert d["msg"] == "검색 성공"
        assert d["data"] == {"key": "value"}

    def test_without_data_excludes_none(self):
        """data가 None이면 to_dict에서 필드가 생략되는지 확인."""
        resp = APIResponse(code="RAG100001", msg="검색 결과 없음")
        d = resp.to_dict()
        assert "data" not in d
        assert d["code"] == "RAG100001"
        assert d["msg"] == "검색 결과 없음"

    def test_explicit_none_excludes(self):
        """data=None을 명시해도 to_dict에서 생략되는지 확인."""
        resp = APIResponse(code="RAG100001", msg="test", data=None)
        d = resp.to_dict()
        assert "data" not in d


class TestSuccessResponse:
    """success_response 헬퍼 테스트."""

    def test_default_code_and_msg(self):
        """기본 코드(SEARCH_SUCCESS)와 기본 메시지 사용 확인."""
        result = success_response(data={"results": []})
        assert result["code"] == "RAG100000"
        assert result["msg"] == "검색 성공"
        assert result["data"] == {"results": []}

    def test_custom_msg(self):
        """커스텀 메시지 오버라이드 확인."""
        result = success_response(data={}, msg="커스텀 메시지")
        assert result["msg"] == "커스텀 메시지"

    def test_custom_code(self):
        """다른 코드 지정 확인."""
        result = success_response(data={}, code=RAGCode.NO_RESULT)
        assert result["code"] == "RAG100001"

    def test_includes_data(self):
        """data가 항상 포함되는지 확인."""
        result = success_response(data={"query": "test"})
        assert "data" in result


class TestErrorResponse:
    """error_response 헬퍼 테스트."""

    def test_default_msg(self):
        """기본 메시지 사용 확인."""
        result = error_response(code=RAGCode.BAD_REQUEST)
        assert result["code"] == "RAG100020"
        assert result["msg"] == "잘못된 요청"

    def test_custom_msg(self):
        """커스텀 메시지 오버라이드 확인."""
        result = error_response(
            code=RAGCode.BAD_REQUEST, msg="잘못된 요청: 입력 벡터 차원 불일치"
        )
        assert result["msg"] == "잘못된 요청: 입력 벡터 차원 불일치"

    def test_no_data_field(self):
        """에러 응답에 data 필드가 없는지 확인."""
        result = error_response(code=RAGCode.INTERNAL_ERROR)
        assert "data" not in result

    def test_reranker_failure(self):
        """리랭커 실패 코드 확인."""
        result = error_response(code=RAGCode.RERANKER_FAILURE)
        assert result["code"] == "RAG100050"
        assert result["msg"] == "리랭커 연동 실패"


class TestNoResultResponse:
    """no_result_response 헬퍼 테스트."""

    def test_code_and_msg(self):
        """코드와 메시지가 올바른지 확인."""
        result = no_result_response()
        assert result["code"] == "RAG100001"
        assert result["msg"] == "검색 결과 없음"

    def test_no_data_field(self):
        """data 필드가 없는지 확인."""
        result = no_result_response()
        assert "data" not in result
