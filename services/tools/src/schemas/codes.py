"""TOL 응답 코드 상수 정의.

코드 형식: TOL + XXYYZZ (6자리)
  - XX: 기능 카테고리 (00=공통, 01=조회, 02=요약)
  - YY: 세부 기능 (01=일반)
  - ZZ: 상태 (00=성공, 20~79=에러/정보)
성공 판별: 뒤 두 자리(ZZ)가 00이면 성공
"""

from enum import Enum


class TOLCode(str, Enum):
    """TOL 표준 응답 코드."""

    # 성공 (ZZ=00)
    SUCCESS_QUERY = "TOL010100"
    SUCCESS_SUMMARY = "TOL020100"

    # 정보
    INFO_TRACE_ID_CREATED = "TOL000021"

    # 예외
    ERROR_LLM_CONNECTION = "TOL020130"
    ERROR_INVALID_SCOPE = "TOL010130"
    ERROR_EXTERNAL_API = "TOL030130"
    ERROR_INTERNAL = "TOL000030"

    def __new__(cls, value: str) -> "TOLCode":
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj._is_success = value.endswith("00")
        return obj

    @property
    def is_success(self) -> bool:
        """뒤 두 자리가 00이면 성공."""
        return self._is_success  # type: ignore[return-value]


class TOLMessage(str, Enum):
    """TOL 표준 응답 메시지."""

    SUCCESS = "요청이 성공했습니다"
    TRACE_ID_CREATED = "TraceID가 존재하지 않아 자동 생성되었습니다."
    LLM_CONNECTION_FAILED = "LLM 프로바이더 응답 실패"
    INVALID_SCOPE = "유효하지 않은 Scope입니다"
    EXTERNAL_API_FAILED = "외부 API 호출 실패"
    INTERNAL_ERROR = "서버 내부 오류"
