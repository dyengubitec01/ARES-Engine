"""TOL 표준 응답 래퍼 모델."""

from typing import Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, model_serializer

from src.schemas.codes import TOLCode, TOLMessage

T = TypeVar("T")


class TOLResponse(BaseModel, Generic[T]):
    """TOL 표준 응답 포맷.

    {
        "code": "TOLxxxxxx",
        "msg": "메시지",
        "data": { ... }  // Optional — None이면 JSON에서 제외
    }
    """

    code: TOLCode
    msg: str
    data: T | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"code": "TOL010100", "msg": "요청이 성공했습니다", "data": None},
            ]
        },
    )

    @model_serializer
    def _serialize(self) -> dict:
        """data가 None이면 응답 JSON에서 제외."""
        result: dict = {"code": self.code.value, "msg": self.msg}
        if self.data is not None:
            result["data"] = self.data
        return result

    @classmethod
    def success(cls, code: TOLCode, data: T | None = None) -> "TOLResponse[T]":
        """성공 응답 생성.

        Args:
            code: TOL 성공 코드 (뒤 2자리가 00이어야 함).
            data: 응답 데이터 (Optional).

        Raises:
            ValueError: code가 성공 코드가 아닐 경우.
        """
        if not code.is_success:
            raise ValueError(f"{code.value}는 성공 코드가 아닙니다 (뒤 2자리가 00이어야 함)")
        return cls(code=code, msg=TOLMessage.SUCCESS.value, data=data)

    @classmethod
    def info(cls, code: TOLCode, msg: TOLMessage) -> "TOLResponse[None]":
        """정보 응답 생성."""
        return cls(code=code, msg=msg.value)

    @classmethod
    def error(cls, code: TOLCode, msg: TOLMessage) -> "TOLResponse[None]":
        """에러 응답 생성."""
        return cls(code=code, msg=msg.value)


def tol_error_json(
    status_code: int, code: TOLCode, msg: TOLMessage,
) -> JSONResponse:
    """TOL 표준 에러 JSONResponse 생성.

    전역 예외 핸들러, 미들웨어 등에서 일관된 에러 응답을 반환할 때 사용.

    Args:
        status_code: HTTP 상태 코드.
        code: TOL 에러 코드.
        msg: TOL 에러 메시지.

    Returns:
        TOL 표준 포맷의 JSONResponse.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code.value,
            "msg": msg.value,
            "data": None,
        },
    )
