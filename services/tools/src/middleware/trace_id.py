"""Trace-ID 추출/생성 미들웨어.

요청 헤더에서 Trace-ID를 추출하거나, 없을 경우 자동 생성한다.
TECH_SPEC 4장 (관측 가능성 및 Trace-ID 전략) 참조.
"""

import logging
import re
import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Trace-ID 헤더 이름
TRACE_ID_HEADER = "X-LF-Trace-ID"

# Parent-ID 헤더 이름 (agent trace의 parent span observation_id)
PARENT_ID_HEADER = "X-LF-Parent-Id"

# Langfuse trace 생성을 건너뛸 경로
_LANGFUSE_SKIP_PATHS = frozenset({"/health"})

# 현재 요청의 Trace-ID를 저장하는 ContextVar
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def get_trace_id() -> str | None:
    """현재 요청의 Trace-ID 반환.

    Returns:
        Trace-ID 문자열 또는 None.
    """
    return trace_id_var.get()


def generate_trace_id() -> str:
    """새로운 Trace-ID 생성.

    Returns:
        UUID4 형식의 Trace-ID.
    """
    return str(uuid.uuid4())


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Trace-ID 미들웨어.

    요청 헤더에서 X-LF-Trace-ID를 추출하고,
    없을 경우 자동 생성하여 응답 헤더에 포함한다.
    Langfuse 설정 시 root span을 OTEL context manager로 감싼다.
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # 헤더에서 Trace-ID 추출 또는 생성
        trace_id = request.headers.get(TRACE_ID_HEADER)
        is_generated = False
        is_external_trace = bool(trace_id)

        if not trace_id:
            trace_id = generate_trace_id()
            is_generated = True

        # ContextVar에 저장 (다른 모듈에서 접근 가능)
        token = trace_id_var.set(trace_id)

        try:
            response = await self._handle_request(
                request, call_next, trace_id, is_external_trace
            )
        finally:
            trace_id_var.reset(token)

        # 응답 헤더에 Trace-ID 추가
        response.headers[TRACE_ID_HEADER] = trace_id

        # 자동 생성된 경우 추가 헤더로 표시
        if is_generated:
            response.headers["X-LF-Trace-ID-Generated"] = "true"

        return response

    async def _call_next_safe(
        self, request: Request, call_next: Callable
    ) -> Response:
        """call_next 호출 및 예외 시 generic_exception_handler 위임."""
        try:
            return await call_next(request)
        except Exception as exc:
            from src.exceptions.handlers import generic_exception_handler

            return await generic_exception_handler(request, exc)

    async def _handle_request(
        self,
        request: Request,
        call_next: Callable,
        trace_id: str,
        is_external_trace: bool,
    ) -> Response:
        """요청 처리. Langfuse 설정 시 root span으로 감싼다.

        Langfuse trace 생성 조건:
        - /health 경로가 아닐 것
        - 외부에서 X-LF-Trace-ID 헤더가 전달되었을 것
        - Langfuse 클라이언트가 설정되어 있을 것
        - trace_id가 유효한 hex 형식일 것 (UUID 36자 또는 hex 32자)
        """
        # /health 또는 외부 trace_id 없으면 Langfuse skip
        if request.url.path in _LANGFUSE_SKIP_PATHS or not is_external_trace:
            return await self._call_next_safe(request, call_next)

        from src.middleware.langfuse import get_langfuse_client

        client = get_langfuse_client()
        if not client:
            return await self._call_next_safe(request, call_next)

        # trace_id 형식 검증: UUID(36자) 또는 32자 hex 허용
        trace_id_clean = trace_id.replace("-", "")
        if not re.fullmatch(r"[0-9a-f]{32}", trace_id_clean):
            return await self._call_next_safe(request, call_next)

        # trace_context 구성 (원본 trace_id 그대로 전달)
        trace_context: dict[str, str] = {"trace_id": trace_id}

        # parent_span_id 전파 (있는 경우에만)
        parent_id = request.headers.get(PARENT_ID_HEADER)
        if parent_id:
            trace_context["parent_span_id"] = parent_id

        logger.debug(
            "Langfuse trace 연결: trace_id=%s, parent_id=%s, path=%s",
            trace_id, parent_id, request.url.path,
        )

        # Langfuse root span + _strip_as_root 래퍼
        from src.middleware.langfuse import strip_as_root

        cm = client.start_as_current_observation(
            as_type="span",
            name="http-request",
            trace_context=trace_context,
            input={"method": request.method, "path": str(request.url.path)},
        )
        with strip_as_root(cm) as root_span:
            # trace_context를 request.state에 저장 (하위 레이어 전파용)
            child_trace_context: dict[str, str] = {"trace_id": trace_id}
            obs_id = getattr(root_span, "id", None)
            if obs_id:
                child_trace_context["parent_span_id"] = obs_id
            request.state.trace_context = child_trace_context
            try:
                response = await call_next(request)
                root_span.update(output={"status_code": response.status_code})
                return response
            except Exception as exc:
                root_span.update(
                    output={"error": type(exc).__name__},
                    level="ERROR",
                )
                from src.exceptions.handlers import generic_exception_handler

                return await generic_exception_handler(request, exc)
