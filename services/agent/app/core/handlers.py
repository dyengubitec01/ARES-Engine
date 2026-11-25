"""
Global Exception Handlers.

전역 예외 핸들러 (Story 1.6)
BusinessException, RequestValidationError, Unhandled Exception 처리.
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.enums import ErrorCode
from app.core.exceptions import BusinessException

logger = structlog.get_logger()


async def business_exception_handler(
    request: Request, exc: BusinessException
) -> JSONResponse:
    """
    Handle BusinessException with dynamic HTTP status code.

    Returns simplified error response with code and msg only.
    """
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "msg": exc.msg,
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle FastAPI/Pydantic RequestValidationError (AC 2.7.7).

    Returns simplified error response without exposing validation details.
    """
    # 검증 실패 시 요청 body + 에러 상세를 로그에 기록
    try:
        body = await request.body()
        body_preview = body.decode("utf-8", errors="replace")[:500]
    except Exception:
        body_preview = "(읽기 실패)"

    errors = [
        {"field": ".".join(str(l) for l in e.get("loc", [])), "msg": e.get("msg", "")}
        for e in exc.errors()
    ]
    logger.warning(
        "request_validation_failed",
        error_code=ErrorCode.VALIDATION_ERROR.code,
        errors=errors,
        request_body=body_preview,
    )

    return JSONResponse(
        status_code=422,
        content={
            "code": ErrorCode.VALIDATION_ERROR.code,
            "msg": ErrorCode.VALIDATION_ERROR.msg,
        },
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Handle all unhandled exceptions.

    Logs error details but returns simplified error response to client.
    """
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": ErrorCode.INTERNAL_ERROR.code,
            "msg": ErrorCode.INTERNAL_ERROR.msg,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers to FastAPI app.

    Args:
        app: FastAPI application instance.
    """
    app.add_exception_handler(BusinessException, business_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
