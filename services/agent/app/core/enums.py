"""
Error Code Definitions.

Enum 기반 에러 코드 관리 (Story 1.6)
HTTP 상태 코드 체계:
- AGT0xxx: 성공 (200)
- AGT4xxx: 클라이언트 에러 (400, 422)
- AGT5xxx: 서버 에러 (500, 502, 503)
"""

from enum import Enum


class ErrorCode(Enum):
    """Centralized error codes with HTTP status mapping."""

    # 성공 (2xx)
    SUCCESS = ("AGT0000", "요청이 성공하였습니다.", 200)

    # 4xxx: 클라이언트 에러 (4xx)
    VALIDATION_ERROR = ("AGT4000", "입력값이 유효하지 않습니다.", 400)
    INVALID_REQUEST = ("AGT4001", "잘못된 요청입니다.", 400)

    # 5xxx: 서버 에러 (5xx)
    INTERNAL_ERROR = ("AGT5000", "내부 서버 오류가 발생했습니다.", 500)
    LLM_CONNECTION = ("AGT5001", "LLM 서버에 연결할 수 없습니다.", 503)
    LLM_RESPONSE = ("AGT5002", "LLM 응답 처리 중 오류가 발생했습니다.", 502)
    RAG_SEARCH = ("AGT5003", "RAG 검색에 실패했습니다.", 503)
    TOOL_EXECUTION = ("AGT5004", "도구 실행에 실패했습니다.", 503)
    ALL_SERVERS_DOWN = ("AGT5010", "일시적으로 서비스를 이용할 수 없습니다.", 503)

    def __init__(self, code: str, msg: str, http_status: int) -> None:
        self._code = code
        self._msg = msg
        self._http_status = http_status

    @property
    def code(self) -> str:
        """Get error code string (e.g., 'AGT5001')."""
        return self._code

    @property
    def msg(self) -> str:
        """Get default error message."""
        return self._msg

    @property
    def http_status(self) -> int:
        """Get HTTP status code."""
        return self._http_status
