"""Scope 검증 미들웨어.

tools.yaml의 endpoint 매핑을 기반으로 기능 API의
Scope 접근 권한을 자동 검증한다.
"""

import logging
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config.loader import get_allowed_scopes
from src.config.tools import ToolConfig, load_tools_config
from src.schemas.codes import TOLCode, TOLMessage
from src.schemas.response import tol_error_json

logger = logging.getLogger(__name__)


class ScopeMiddleware(BaseHTTPMiddleware):
    """Scope 검증 미들웨어.

    tools.yaml에 endpoint가 등록된 기능 API에 대해
    X-TOL-Scope 헤더를 자동으로 검증한다.
    tools.yaml에 없는 경로(예: /health, /v1/tools)는 통과시킨다.
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        tool = load_tools_config().get_tool_by_endpoint(request.url.path)

        if tool is not None:
            scope = request.headers.get("x-tol-scope")
            rejection = self._check_scope(scope, tool)
            if rejection is not None:
                return rejection

        return await call_next(request)

    def _check_scope(
        self, scope: str | None, tool: ToolConfig
    ) -> JSONResponse | None:
        """Scope 유효성 검사. 실패 시 400 응답, 성공 시 None."""
        allowed_scopes = get_allowed_scopes()

        if scope is None:
            return _reject(
                scope="(미전달)", allowed=allowed_scopes, tool_name=tool.name,
            )

        if scope not in allowed_scopes:
            return _reject(
                scope=scope, allowed=allowed_scopes, tool_name=tool.name,
            )

        if scope not in tool.scopes:
            return _reject(
                scope=scope, allowed=list(tool.scopes), tool_name=tool.name,
            )

        logger.info("Scope 검증 통과: scope=%s, tool=%s", scope, tool.name)
        return None


def _reject(
    scope: str, allowed: list[str], tool_name: str,
) -> JSONResponse:
    """Scope 거부 시 TOL 표준 400 응답 반환."""
    logger.warning(
        "Scope 거부: scope=%s, tool=%s, allowed=%s",
        scope, tool_name, allowed,
    )

    return tol_error_json(400, TOLCode.ERROR_INVALID_SCOPE, TOLMessage.INVALID_SCOPE)
