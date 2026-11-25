"""Langfuse 분산 트레이싱 모듈."""

import logging
import uuid
from contextlib import AbstractContextManager, contextmanager, nullcontext

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import PARENT_ID_HEADER, TRACE_ID_HEADER, get_settings

logger = logging.getLogger(__name__)

_langfuse_client = None


def get_langfuse_client() -> object | None:
    """Settings 기반 Langfuse 클라이언트를 생성한다.

    LANGFUSE_ENABLED=false이거나 LANGFUSE_PUBLIC_KEY가 비어있으면 None 반환.
    """
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    settings = get_settings()
    if not settings.LANGFUSE_ENABLED:
        logger.info("Langfuse 비활성화 상태 (LANGFUSE_ENABLED=false)")
        return None
    if not settings.LANGFUSE_PUBLIC_KEY:
        logger.warning("LANGFUSE_PUBLIC_KEY가 비어있어 Langfuse 비활성화")
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
        logger.info("Langfuse 클라이언트 초기화 완료: host=%s", settings.LANGFUSE_HOST)
    except Exception as exc:
        logger.warning("Langfuse 클라이언트 생성 실패: %s", exc)
        return None

    return _langfuse_client


def shutdown_langfuse() -> None:
    """Langfuse 클라이언트를 flush하고 정리한다."""
    global _langfuse_client
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            logger.info("Langfuse flush 완료")
        except Exception as exc:
            logger.warning("Langfuse flush 실패 — 정상 종료 진행: %s", exc)
        _langfuse_client = None


def _reset_langfuse_client() -> None:
    """테스트 격리용: 전역 Langfuse 클라이언트를 리셋한다."""
    global _langfuse_client
    _langfuse_client = None


@contextmanager
def _strip_as_root(cm):
    """AS_ROOT attribute를 제거하여 trace name 덮어쓰기를 방지하는 래퍼."""
    with cm as span:
        try:
            span._otel_span.set_attribute("langfuse.internal.as_root", False)
        except Exception:
            pass
        yield span


def observe(*, name: str, as_type: str = "span", **kwargs) -> AbstractContextManager:
    """Langfuse observation context manager.

    trace_context가 있으면 cross-service 연결 후 AS_ROOT를 제거하여
    Langfuse 서버의 trace name 덮어쓰기를 방지한다.
    Langfuse 비활성화 시 nullcontext() 반환.
    """
    client = get_langfuse_client()
    if client is None:
        return nullcontext()
    try:
        cm = client.start_as_current_observation(
            as_type=as_type, name=name, **kwargs
        )
        if "trace_context" in kwargs:
            return _strip_as_root(cm)
        return cm
    except Exception as exc:
        logger.warning("Langfuse observation 생성 실패: %s", exc)
        return nullcontext()


def safe_update_span(span, **kwargs) -> None:
    """span.update() 안전 호출. span이 None이거나 update 실패 시 무시."""
    if span is None:
        return
    try:
        span.update(**kwargs)
    except Exception as exc:
        logger.warning("Langfuse span 업데이트 실패: %s", exc)


class LangfuseMiddleware(BaseHTTPMiddleware):
    """모든 요청에 X-LF-Trace-ID를 할당하고 Langfuse Trace를 생성하는 미들웨어."""

    def __init__(self, app, langfuse_client=None):
        super().__init__(app)
        self._langfuse = langfuse_client

    async def dispatch(self, request: Request, call_next) -> Response:
        """X-LF-Trace-ID를 승계 또는 신규 생성하고, Langfuse Trace를 기록한다."""
        # /health는 로그·트레이싱 없이 바로 통과
        if request.url.path == "/health":
            return await call_next(request)

        trace_id_from_header = request.headers.get(TRACE_ID_HEADER)
        if trace_id_from_header:
            trace_id = trace_id_from_header
            logger.info("X-LF-Trace-ID 헤더 수신: %s", trace_id)
        else:
            trace_id = uuid.uuid4().hex
            logger.debug("X-LF-Trace-ID 헤더 없음 — 서버에서 생성: %s", trace_id)
        request.state.trace_id = trace_id
        request.state.parent_observation_id = request.headers.get(PARENT_ID_HEADER)
        request.state.langfuse_span = None

        if not trace_id_from_header:
            response = await call_next(request)
            response.headers[TRACE_ID_HEADER] = trace_id
            return response

        response = await self._handle_request(request, call_next)
        response.headers[TRACE_ID_HEADER] = trace_id
        return response

    async def _handle_request(
        self, request: Request, call_next
    ) -> Response:
        """Langfuse context manager로 root span을 생성하고 요청을 처리한다."""
        if self._langfuse is None:
            return await call_next(request)

        langfuse_trace_id = request.state.trace_id
        parent_id = request.state.parent_observation_id
        logger.info(
            "Langfuse trace 생성 — trace_id: %s, parent_id: %s",
            langfuse_trace_id,
            parent_id,
        )
        trace_context = {"trace_id": langfuse_trace_id}
        if parent_id:
            trace_context["parent_span_id"] = parent_id
        try:
            cm = self._langfuse.start_as_current_observation(
                as_type="span",
                name="rag-search",
                trace_context=trace_context,
                input={"method": request.method, "path": request.url.path},
            )
        except Exception as exc:
            logger.warning(
                "Langfuse trace 생성 실패 — 요청은 정상 진행: %s", exc
            )
            return await call_next(request)

        with _strip_as_root(cm) as root_span:
            request.state.langfuse_span = root_span
            response = await call_next(request)
            try:
                root_span.update(output={"status_code": response.status_code})
            except Exception as exc:
                logger.warning("Langfuse span 업데이트 실패: %s", exc)
            return response
