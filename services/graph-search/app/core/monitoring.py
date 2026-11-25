"""Langfuse 계측 — 미들웨어 + child span 헬퍼.

Agent가 보내는 X-LF-Trace-ID / X-LF-Parent-Id를 받아, 부모 trace 아래에
`rag-graph-search` root span을 nest하고, 3-Step 파이프라인을 child span으로 계측한다.
LANGFUSE_ENABLED=false 또는 미설치 시 전부 무해한 no-op.

계측 규약은 rag-search 서버와 동일 (같은 trace 트리에 합쳐지도록).
"""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager, nullcontext
from functools import lru_cache

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import PARENT_ID_HEADER, TRACE_ID_HEADER, get_settings

logger = logging.getLogger(__name__)


class _NoopSpan:
    """Langfuse 비활성 시 span 자리를 채우는 no-op. update()·id 접근 안전."""

    id = None

    def update(self, *args, **kwargs) -> None:
        pass


def noop_span():
    """항상 사용 가능한 no-op span 컨텍스트."""
    return nullcontext(_NoopSpan())


@lru_cache
def get_langfuse_client():
    """Langfuse 클라이언트(싱글턴). 비활성/미설치 시 None."""
    settings = get_settings()
    if not settings.LANGFUSE_ENABLED:
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
        )
    except Exception as exc:  # pragma: no cover - 방어적
        logger.warning("Langfuse 초기화 실패 — 비활성화: %s", exc)
        return None


def shutdown_langfuse() -> None:
    client = get_langfuse_client()
    if client is not None:
        try:
            client.flush()
        except Exception as exc:  # pragma: no cover
            logger.warning("Langfuse flush 실패: %s", exc)


@contextmanager
def _strip_as_root(cm):
    """Langfuse v3 함정 우회: trace_context로 nest해도 SDK가 span을 root로
    표시해 별도 trace로 뜨는 걸 방지한다. cross-service 계측 시 필수."""
    with cm as span:
        try:
            span._otel_span.set_attribute("langfuse.internal.as_root", False)
        except Exception:
            pass
        yield span


def observe(*, name: str, as_type: str = "span", **kwargs):
    """child span 컨텍스트 생성. 비활성/실패 시 no-op.

    trace_context가 kwargs에 있으면 _strip_as_root로 감싸 부모 span에 nest한다.
    """
    client = get_langfuse_client()
    if client is None:
        return noop_span()
    try:
        cm = client.start_as_current_observation(as_type=as_type, name=name, **kwargs)
        if "trace_context" in kwargs:
            return _strip_as_root(cm)
        return cm
    except Exception as exc:  # pragma: no cover
        logger.warning("Langfuse span 생성 실패: %s", exc)
        return noop_span()


class LangfuseMiddleware(BaseHTTPMiddleware):
    """트레이스 헤더 수신 + 부모 trace 아래 rag-graph-search root span nest."""

    def __init__(self, app, langfuse_client=None) -> None:
        super().__init__(app)
        self._langfuse = langfuse_client

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        trace_id_from_header = request.headers.get(TRACE_ID_HEADER)
        trace_id = trace_id_from_header or uuid.uuid4().hex

        request.state.trace_id = trace_id
        request.state.parent_observation_id = request.headers.get(PARENT_ID_HEADER)
        request.state.langfuse_span = None

        # 헤더가 없으면 nest할 부모가 없으므로 root span 생성 없이 통과
        if not trace_id_from_header:
            response = await call_next(request)
            response.headers[TRACE_ID_HEADER] = trace_id
            return response

        response = await self._handle_request(request, call_next)
        response.headers[TRACE_ID_HEADER] = trace_id
        return response

    async def _handle_request(self, request: Request, call_next):
        """부모 trace 아래에 rag-graph-search root span을 nest."""
        if self._langfuse is None:
            return await call_next(request)

        trace_context = {"trace_id": request.state.trace_id}
        if request.state.parent_observation_id:
            trace_context["parent_span_id"] = request.state.parent_observation_id

        cm = self._langfuse.start_as_current_observation(
            as_type="span",
            name="rag-graph-search",
            trace_context=trace_context,
            input={"method": request.method, "path": request.url.path},
        )
        with _strip_as_root(cm) as root_span:
            request.state.langfuse_span = root_span
            response = await call_next(request)
            try:
                root_span.update(output={"status_code": response.status_code})
            except Exception:
                pass
            return response
