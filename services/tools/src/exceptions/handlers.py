"""TOL 전역 예외 핸들러.

Layered Architecture 원칙에 따라, Provider 계층의 비즈니스 예외를
TOL 표준 응답으로 변환한다. (TECH_SPEC 6.3)
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.exceptions.exceptions import (
    ExternalAPIError,
    InvalidScopeError,
    LLMProviderError,
)
from src.schemas.codes import TOLCode, TOLMessage
from src.schemas.response import tol_error_json

logger = logging.getLogger(__name__)


async def llm_provider_error_handler(
    request: Request,
    exc: LLMProviderError,
) -> JSONResponse:
    """LLMProviderError → TOL 표준 응답 (HTTP 503).

    Args:
        request: FastAPI 요청 객체.
        exc: Failover 체인 소진 예외.

    Returns:
        TOL 표준 JSON 응답 (TOL020130).
    """
    logger.error(
        "Graceful Degradation: role=%s, chain=%s, detail=%s",
        exc.role, exc.chain, exc.detail,
    )

    return JSONResponse(
        status_code=503,
        content={
            "code": TOLCode.ERROR_LLM_CONNECTION.value,
            "msg": TOLMessage.LLM_CONNECTION_FAILED.value,
            "data": None,
        },
    )


async def invalid_scope_error_handler(
    request: Request,
    exc: InvalidScopeError,
) -> JSONResponse:
    """InvalidScopeError → TOL 표준 응답 (HTTP 400).

    Args:
        request: FastAPI 요청 객체.
        exc: 유효하지 않은 Scope 예외.

    Returns:
        TOL 표준 JSON 응답 (TOL010130).
    """
    logger.warning(
        "Invalid Scope: scope=%s, allowed=%s",
        exc.scope, exc.allowed_scopes,
    )

    return tol_error_json(400, TOLCode.ERROR_INVALID_SCOPE, TOLMessage.INVALID_SCOPE)


async def external_api_error_handler(
    request: Request,
    exc: ExternalAPIError,
) -> JSONResponse:
    """ExternalAPIError → TOL 표준 응답 (HTTP 502).

    Args:
        request: FastAPI 요청 객체.
        exc: 외부 API 호출 실패 예외.

    Returns:
        TOL 표준 JSON 응답 (TOL030130).
    """
    logger.error(
        "External API Error: api=%s, status=%s, detail=%s",
        exc.api_name, exc.status_code, exc.detail,
    )

    return JSONResponse(
        status_code=502,
        content={
            "code": TOLCode.ERROR_EXTERNAL_API.value,
            "msg": TOLMessage.EXTERNAL_API_FAILED.value,
            "data": None,
        },
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """예상치 못한 예외 → TOL 표준 응답 (HTTP 500).

    FastAPI 기본 500 응답 대신 TOL 표준 포맷으로 반환한다.

    Args:
        request: FastAPI 요청 객체.
        exc: 처리되지 않은 예외.

    Returns:
        TOL 표준 JSON 응답 (TOL000030).
    """
    logger.exception("Unhandled exception: %s", exc)

    return tol_error_json(500, TOLCode.ERROR_INTERNAL, TOLMessage.INTERNAL_ERROR)


def register_exception_handlers(app: FastAPI) -> None:
    """전역 예외 핸들러를 FastAPI 앱에 등록.

    구체적 예외를 먼저, catch-all을 마지막에 등록한다.

    Args:
        app: FastAPI 앱 인스턴스.
    """
    app.add_exception_handler(ExternalAPIError, external_api_error_handler)
    app.add_exception_handler(InvalidScopeError, invalid_scope_error_handler)
    app.add_exception_handler(LLMProviderError, llm_provider_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
