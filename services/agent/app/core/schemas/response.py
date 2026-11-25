"""
Standard Response Format.

표준 응답 포맷 (DESIGN_SPEC.md Section 5.2)
CommonResponse: ErrorCode Enum 기반 팩토리 메서드 제공 (Story 1.6)
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.enums import ErrorCode

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    """
    Standard API Response Wrapper.

    모든 API 응답(Streaming 제외)은 이 포맷을 사용.

    Examples:
        성공 응답:
        {
            "code": "AGT1211",
            "msg": "회원 정보 조회 성공",
            "data": {"id": "user_1", "name": "Hong"}
        }

        데이터 없는 성공:
        {
            "code": "AGT1210",
            "msg": "회원 정보 수정 성공"
        }
    """

    code: str = Field(
        ...,
        description="서버 식별자(AGT) + 커스텀 숫자(4자리)",
        examples=["AGT0000", "AGT1211"],
    )
    msg: str = Field(..., description="성공 또는 에러 메시지")
    data: T | None = Field(default=None, description="실제 데이터 Payload")


class CommonResponse(BaseModel, Generic[T]):
    """
    Common API Response with ErrorCode factory methods.

    ErrorCode Enum과 통합된 응답 생성 (Story 1.6).

    Examples:
        성공 응답:
        >>> CommonResponse.success(data={"id": 1})
        {"code": "AGT0000", "msg": "요청이 성공하였습니다.", "data": {"id": 1}}

        에러 응답:
        >>> CommonResponse.error(ErrorCode.VALIDATION_ERROR)
        {"code": "AGT4000", "msg": "입력값이 유효하지 않습니다.", "data": null}
    """

    code: str = Field(
        ...,
        description="서버 식별자(AGT) + 커스텀 숫자(4자리)",
        examples=["AGT0000", "AGT4000"],
    )
    msg: str = Field(..., description="성공 또는 에러 메시지")
    data: T | None = Field(default=None, description="실제 데이터 Payload")

    @classmethod
    def success(
        cls,
        data: T | None = None,
        error_code: ErrorCode = ErrorCode.SUCCESS,
    ) -> "CommonResponse[T]":
        """
        Create a success response.

        Args:
            data: Response payload data.
            error_code: ErrorCode enum member (default: SUCCESS).

        Returns:
            CommonResponse instance with success data.
        """
        return cls(code=error_code.code, msg=error_code.msg, data=data)

    @classmethod
    def error(
        cls,
        error_code: ErrorCode,
        detail: str | None = None,
    ) -> "CommonResponse[None]":
        """
        Create an error response.

        Args:
            error_code: ErrorCode enum member defining code and msg.
            detail: Optional additional detail to append to message.

        Returns:
            CommonResponse instance with error information.
        """
        msg = f"{error_code.msg}: {detail}" if detail else error_code.msg
        return cls(code=error_code.code, msg=msg, data=None)


class HealthData(BaseModel):
    """Health check response data."""

    status: str = "healthy"


def success_response(
    code: str,
    msg: str,
    data: Any = None,
) -> dict[str, Any]:
    """Create a success response dictionary."""
    response = {"code": code, "msg": msg}
    if data is not None:
        response["data"] = data
    return response


def error_response(
    code: str = "AGT5000",
    msg: str = "Internal Server Error",
    data: Any = None,
) -> dict[str, Any]:
    """Create an error response dictionary."""
    response = {"code": code, "msg": msg}
    if data is not None:
        response["data"] = data
    return response
