"""
Business Exception Definition.

단일 비즈니스 예외 클래스 (Story 1.6)
ErrorCode Enum과 함께 사용하여 일관된 에러 처리 제공.
"""

from app.core.enums import ErrorCode


class BusinessException(Exception):
    """
    Single business exception class for all application errors.

    Usage:
        # 기본 사용
        raise BusinessException(ErrorCode.VALIDATION_ERROR)

        # 상세 메시지 추가
        raise BusinessException(ErrorCode.LLM_CONNECTION, detail="primary 서버 타임아웃")
    """

    def __init__(self, error_code: ErrorCode, detail: str | None = None) -> None:
        """
        Initialize BusinessException.

        Args:
            error_code: ErrorCode enum member defining code, msg, and http_status.
            detail: Optional additional detail message.
        """
        self.error_code = error_code
        self.detail = detail
        super().__init__(error_code.msg)

    @property
    def code(self) -> str:
        """Get error code string."""
        return self.error_code.code

    @property
    def msg(self) -> str:
        """Get error message (with detail if provided)."""
        if self.detail:
            return f"{self.error_code.msg}: {self.detail}"
        return self.error_code.msg

    @property
    def http_status(self) -> int:
        """Get HTTP status code."""
        return self.error_code.http_status
