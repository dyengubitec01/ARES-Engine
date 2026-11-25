"""Langfuse 연동 모듈.

관측성(Observability)을 위한 Langfuse 클라이언트 초기화 및 트레이싱 기능.
TECH_SPEC 4장 (관측 가능성 및 Trace-ID 전략) 참조.
"""

import logging
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Generator

from langfuse import Langfuse

from src.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_langfuse_client() -> Langfuse | None:
    """Langfuse 클라이언트 싱글턴 반환.

    환경변수가 설정되지 않은 경우 None 반환.

    Returns:
        Langfuse 클라이언트 또는 None.
    """
    settings = get_settings()

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning(
            "Langfuse 환경변수가 설정되지 않았습니다. 트레이싱이 비활성화됩니다."
        )
        return None

    try:
        client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or None,
        )
        logger.info("Langfuse 클라이언트 초기화 완료")
        return client
    except Exception as e:
        logger.error("Langfuse 클라이언트 초기화 실패: %s", e)
        return None


class ManagedSpan:
    """Context manager 생명주기를 관리하는 span wrapper.

    start_as_current_observation()의 cm을 보관하고,
    end() 호출 시 cm.__exit__()로 정상 종료한다.
    이를 통해 Latency 기록과 Output flush가 보장된다.
    """

    def __init__(self, span: Any, cm: Any) -> None:
        self._span = span
        self._cm = cm

    def update(self, **kwargs: Any) -> None:
        """span 속성 업데이트."""
        self._span.update(**kwargs)

    def end(self) -> None:
        """span 종료 및 context manager 정리."""
        if self._cm:
            self._cm.__exit__(None, None, None)
            self._cm = None


def create_span(
    name: str,
    input_data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    trace_context: dict[str, str] | None = None,
) -> ManagedSpan | None:
    """cross-service trace에 연결된 child span 생성.

    trace_context가 없으면 span을 생성하지 않는다 (독립 observation 방지).
    에이전트가 X-LF-Trace-ID 헤더를 전달한 요청에서만 Langfuse에 기록된다.

    Args:
        name: span 이름.
        input_data: 입력 데이터.
        metadata: 추가 메타데이터.
        trace_context: Langfuse trace 연결 정보
            (trace_id, parent_span_id 등).

    Returns:
        ManagedSpan 래퍼 또는 None.
    """
    if not trace_context:
        return None

    client = get_langfuse_client()
    if not client:
        return None

    try:
        cm = client.start_as_current_observation(
            as_type="span",
            name=name,
            trace_context=trace_context,
            input=input_data,
            metadata=metadata or {},
        )
        span = cm.__enter__()
        try:
            span._otel_span.set_attribute(
                "langfuse.internal.as_root", False
            )
        except Exception:
            pass
        return ManagedSpan(span, cm)
    except Exception as e:
        logger.error("Langfuse span 생성 실패: %s", e)
        return None


def create_generation(
    name: str,
    model: str,
    input_data: dict[str, Any] | None = None,
    output_data: str | None = None,
    metadata: dict[str, Any] | None = None,
    trace_context: dict[str, str] | None = None,
) -> Any:
    """현재 OTEL context의 child generation 생성.

    trace_context가 없으면 generation을 생성하지 않는다 (독립 observation 방지).
    TraceIDMiddleware가 설정한 root span 하위에 자동 nesting된다.

    Args:
        name: generation 이름.
        model: 사용된 모델명.
        input_data: 입력 프롬프트/메시지.
        output_data: LLM 응답.
        metadata: 추가 메타데이터.
        trace_context: Langfuse trace 연결 정보 (cross-service).

    Returns:
        Langfuse generation 객체 또는 None.
    """
    if not trace_context:
        return None
    client = get_langfuse_client()
    if not client:
        return None

    try:
        return client.start_observation(
            name=name,
            as_type="generation",
            model=model,
            input=input_data,
            output=output_data,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.error("Langfuse generation 생성 실패: %s", e)
        return None


@contextmanager
def strip_as_root(cm: Any) -> Generator[Any, None, None]:
    """AS_ROOT attribute를 제거하여 trace name 덮어쓰기를 방지하는 래퍼.

    Langfuse SDK v3에서 start_as_current_observation(trace_context=...)를
    호출하면 내부적으로 AS_ROOT=True가 설정되어, 원래 trace name이 현재
    span name으로 덮어쓰여진다. 이를 False로 재설정하여 방지한다.
    """
    with cm as span:
        try:
            span._otel_span.set_attribute("langfuse.internal.as_root", False)
        except Exception:
            pass
        yield span


def flush_langfuse() -> None:
    """Langfuse 버퍼 플러시.

    서버 종료 시 호출하여 미전송 데이터를 전송한다.
    """
    client = get_langfuse_client()
    if client:
        try:
            client.flush()
            logger.info("Langfuse 버퍼 플러시 완료")
        except Exception as e:
            logger.error("Langfuse 플러시 실패: %s", e)
