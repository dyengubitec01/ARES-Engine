"""표준 응답 규격 및 커스텀 코드 체계.

코드 형식: [ServerPrefix(3)][Major(2)][Middle(2)][Minor(2)]
- Server Prefix: RAG
- Major 10: 검색/Search
- Middle 00: 기본/General
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel


class RAGCode(str, Enum):
    """RAG 서버 커스텀 응답 코드."""

    SEARCH_SUCCESS = "RAG100000"
    NO_RESULT = "RAG100001"
    BAD_REQUEST = "RAG100020"
    EMBEDDING_FAILURE = "RAG100040"
    RERANKER_FAILURE = "RAG100050"
    VECTOR_STORE_FAILURE = "RAG100060"
    INTERNAL_ERROR = "RAG100099"

    @property
    def default_message(self) -> str:
        """코드에 대응하는 기본 메시지 반환."""
        return _CODE_MESSAGES[self]


_CODE_MESSAGES: dict[RAGCode, str] = {
    RAGCode.SEARCH_SUCCESS: "검색 성공",
    RAGCode.NO_RESULT: "검색 결과 없음",
    RAGCode.BAD_REQUEST: "잘못된 요청",
    RAGCode.EMBEDDING_FAILURE: "임베딩 연동 실패",
    RAGCode.RERANKER_FAILURE: "리랭커 연동 실패",
    RAGCode.VECTOR_STORE_FAILURE: "벡터 스토어 연동 실패",
    RAGCode.INTERNAL_ERROR: "서버 내부 오류",
}


class APIResponse(BaseModel):
    """표준 API 응답 모델.

    모든 엔드포인트는 이 형식으로 응답한다.
    data가 None이면 JSON 직렬화 시 필드 자체를 생략한다.
    """

    code: str
    msg: str
    data: Optional[Any] = None

    model_config = {"json_schema_extra": {"examples": []}, "populate_by_name": True}

    def to_dict(self) -> dict:
        """exclude_none=True로 직렬화된 dict 반환."""
        return self.model_dump(exclude_none=True)


def success_response(
    data: Any,
    code: RAGCode = RAGCode.SEARCH_SUCCESS,
    msg: str | None = None,
) -> dict:
    """성공 응답 생성.

    msg가 None이면 RAGCode에 매핑된 기본 메시지를 사용한다.
    """
    return APIResponse(
        code=code.value,
        msg=msg or code.default_message,
        data=data,
    ).to_dict()


def error_response(
    code: RAGCode,
    msg: str | None = None,
) -> dict:
    """에러 응답 생성.

    msg가 None이면 RAGCode에 매핑된 기본 메시지를 사용한다.
    """
    return APIResponse(
        code=code.value,
        msg=msg or code.default_message,
    ).to_dict()


def no_result_response() -> dict:
    """검색 결과 없음 전용 응답."""
    return APIResponse(
        code=RAGCode.NO_RESULT.value,
        msg=RAGCode.NO_RESULT.default_message,
    ).to_dict()
