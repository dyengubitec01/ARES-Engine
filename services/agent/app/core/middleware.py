"""
FastAPI 미들웨어: request_id 생성 + Access Log (ADR-004).

역할:
1. 요청 시작 시 UUID v4로 request_id 생성 (서버 내부 전용)
2. structlog.contextvars에 request_id, method, path 바인딩
3. 요청 완료 후 Access Log 1줄 기록 (Tier 1)
4. 요청 시작 시 contextvars 클리어 (이전 요청 컨텍스트 누수 방지)

등록:
    main.py에서 app.add_middleware(LoggingMiddleware) 호출
"""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

access_logger = structlog.get_logger("access")


# Access Log 및 request_id 생성을 건너뛸 경로
_SKIP_LOG_PATHS = frozenset({"/health", "/health/"})


class LoggingMiddleware(BaseHTTPMiddleware):
    """request_id 생성 + Access Log 미들웨어."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # 이전 요청 컨텍스트 누수 방지
        structlog.contextvars.clear_contextvars()

        # health check는 로깅/request_id 생성 없이 통과
        if request.url.path in _SKIP_LOG_PATHS:
            return await call_next(request)

        # request_id 생성 및 바인딩
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        # 클라이언트 IP 추출
        client_ip = (
            request.client.host if request.client else "unknown"
        )

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round(
                (time.perf_counter() - start_time) * 1000, 2
            )
            access_logger.error(
                "request_failed",
                status_code=500,
                duration_ms=duration_ms,
                client_ip=client_ip,
            )
            raise

        duration_ms = round(
            (time.perf_counter() - start_time) * 1000, 2
        )
        access_logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=client_ip,
        )

        return response
