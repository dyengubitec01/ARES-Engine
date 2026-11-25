"""
트레이싱 유틸리티 - LangFuse trace_id / observation_id 추출.

Story 2.8 AC 2.8.10: RunnableConfig에서 LangFuse trace 정보를 추출하여
외부 서비스 호출 시 헤더로 전달.

헤더 규격:
- X-LF-Trace-ID: 같은 trace에 합류하기 위한 trace_id
- X-LF-Parent-Id: trace 안에서 parent span으로 붙기 위한 observation_id
"""

from dataclasses import dataclass

from langchain_core.runnables import RunnableConfig


@dataclass
class TraceContext:
    """LangFuse cross-service 트레이싱에 필요한 컨텍스트.

    Attributes:
        trace_id: LangFuse trace_id (같은 trace에 합류).
        observation_id: 현재 노드의 LangFuse observation_id (parent span).
    """

    trace_id: str | None = None
    observation_id: str | None = None


def extract_trace_context(config: RunnableConfig) -> TraceContext:
    """RunnableConfig에서 LangFuse trace_id와 observation_id를 추출한다.

    LangGraph 노드에서 호출하면, 현재 노드의 callback manager와
    LangFuse handler로부터 cross-service 트레이싱에 필요한 값을 추출한다.

    Args:
        config: LangGraph 노드에 전달된 RunnableConfig.

    Returns:
        TraceContext(trace_id, observation_id). 추출 실패 시 필드가 None.
    """
    ctx = TraceContext()

    callbacks = config.get("callbacks")
    if callbacks is None:
        return ctx

    handlers = getattr(callbacks, "handlers", callbacks)
    if handlers is None:
        return ctx

    # LangFuse handler 찾기
    handler = _find_langfuse_handler(handlers)
    if handler is None:
        return ctx

    # 1) trace_id 추출
    ctx.trace_id = _extract_trace_id(handler)

    # 2) observation_id 추출: callback manager의 parent_run_id → handler.runs 매핑
    parent_run_id = getattr(callbacks, "parent_run_id", None)
    if parent_run_id is not None:
        runs = getattr(handler, "runs", {})
        obs = runs.get(parent_run_id)
        if obs is not None:
            ctx.observation_id = getattr(obs, "id", None)

    return ctx


def _find_langfuse_handler(handlers):
    """handlers 목록에서 LangFuse handler를 찾는다."""
    try:
        for cb in handlers:
            # SDK v2: CallbackHandler, SDK v3: LangchainCallbackHandler
            if hasattr(cb, "last_trace_id") or hasattr(cb, "get_trace_id"):
                return cb
    except TypeError:
        pass
    return None


def _extract_trace_id(handler) -> str | None:
    """LangFuse handler에서 trace_id를 추출한다."""
    # SDK v2
    if hasattr(handler, "get_trace_id"):
        return handler.get_trace_id()
    if hasattr(handler, "trace_id"):
        return handler.trace_id
    # SDK v3
    if hasattr(handler, "last_trace_id"):
        tid = handler.last_trace_id
        if tid is not None:
            return tid
    return None
