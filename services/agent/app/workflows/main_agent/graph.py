"""
Main Agent Graph - LangGraph 워크플로우 정의.

Story 2.1: LangGraph 기본 워크플로우 구조 설정
Story 2.5: Retriever 노드 추가
Story 2.8: Intent Router + 조건부 엣지 + fan-out/fan-in
StateGraph를 사용하여 노드와 엣지를 정의하고 컴파일한다.

그래프 구조:
    START → rewriter → router ─┬─ (rag)  → retriever ──────→ synthesizer → END
                                ├─ (tool) → tool_executor ──→ synthesizer → END
                                └─ (both) → retriever ∥ tool_executor → synthesizer → END
"""

import threading
import time
from typing import Any, cast

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.tracing import tracing
from app.workflows.main_agent.nodes import (
    retriever,
    rewriter,
    router,
    synthesizer,
    tool_executor,
)
from app.workflows.main_agent.state import AgentState, create_initial_state

logger = structlog.get_logger()


def build_graph() -> StateGraph:
    """
    Main Agent 워크플로우 그래프를 구성한다.

    Returns:
        구성된 StateGraph (컴파일 전).
    """
    # StateGraph 생성 (AgentState를 상태 스키마로 사용)
    graph = StateGraph(AgentState)

    # 노드 추가
    graph.add_node("rewriter", rewriter)
    graph.add_node("router", router)
    graph.add_node("retriever", retriever)
    graph.add_node("tool_executor", tool_executor)
    graph.add_node("synthesizer", synthesizer)

    # 엣지 정의 (Story 2.8)
    graph.add_edge(START, "rewriter")
    graph.add_edge("rewriter", "router")

    # router → retriever | tool_executor | both | direct (조건부 + fan-out)
    graph.add_conditional_edges("router", route_by_intent, {
        "rag": "retriever",
        "tool": "tool_executor",
        "direct": "synthesizer",
    })

    # retriever, tool_executor → synthesizer (fan-in)
    graph.add_edge("retriever", "synthesizer")
    graph.add_edge("tool_executor", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph


def route_by_intent(state: AgentState) -> str | list[str]:
    """router 노드의 route 결과에 따라 다음 노드를 결정한다.

    Args:
        state: 현재 워크플로우 상태.

    Returns:
        "rag", "tool", "direct", 또는 ["rag", "tool"] (fan-out 병렬 실행).
    """
    route = state.get("route", "rag")
    if route == "both":
        return ["rag", "tool"]  # fan-out: 두 노드 병렬 실행
    return route


def compile_graph() -> CompiledStateGraph:
    """
    워크플로우 그래프를 컴파일하여 실행 가능한 Runnable을 반환한다.

    Returns:
        컴파일된 그래프 (Runnable 인터페이스).
    """
    graph = build_graph()
    return graph.compile()


# 컴파일된 그래프 싱글톤 (스레드 안전)
_compiled_graph: CompiledStateGraph | None = None
_graph_lock = threading.Lock()


def get_compiled_graph() -> CompiledStateGraph:
    """
    컴파일된 그래프 싱글톤을 반환한다 (스레드 안전).

    Returns:
        컴파일된 그래프.
    """
    global _compiled_graph
    if _compiled_graph is None:
        with _graph_lock:
            # Double-checked locking
            if _compiled_graph is None:
                _compiled_graph = compile_graph()
    return _compiled_graph


# NOTE: 현재 미사용. chat.py에서 astream_events를 직접 사용 중.
#       신규 필드(user_depts 등)가 반영되지 않은 상태이므로 사용 시 최신화 필요.
async def run_workflow(
    query: str,
    session_id: str,
    history: list[dict] | None = None,
    user_id: str | None = None,
    trace_metadata: dict[str, Any] | None = None,
) -> AgentState:
    """
    워크플로우를 실행하고 최종 상태를 반환한다.

    Args:
        query: 사용자의 질문.
        session_id: 세션 식별자.
        history: 대화 이력 (기본값: 빈 리스트).
        user_id: 사용자 식별자 (LangFuse 트레이싱용).
        trace_metadata: 추가 트레이스 메타데이터.

    Returns:
        워크플로우 실행 후 최종 AgentState.

    Raises:
        ValueError: query 또는 session_id가 비어있을 때.
        Exception: 워크플로우 실행 중 에러 발생 시.
    """
    # 입력 검증
    if not query or not query.strip():
        raise ValueError("query cannot be empty")
    if not session_id or not session_id.strip():
        raise ValueError("session_id cannot be empty")

    graph = get_compiled_graph()
    initial_state = create_initial_state(
        query=query,
        session_id=session_id,
        history=history,
    )

    query_preview = query[:50] + "..." if len(query) > 50 else query
    logger.info("workflow_started", session_id=session_id, query_preview=query_preview)

    # LangFuse 트레이싱 설정
    workflow_metadata = {"workflow": "main_agent", "query": query_preview}
    if trace_metadata:
        workflow_metadata.update(trace_metadata)

    config = tracing.get_langfuse_config(
        session_id=session_id,
        user_id=user_id,
        tags=["workflow", "main_agent"],
        metadata=workflow_metadata,
        run_name="agent",
    )

    workflow_start = time.perf_counter()
    try:
        final_state = await graph.ainvoke(initial_state, config=config)
        duration_ms = round((time.perf_counter() - workflow_start) * 1000, 2)
        logger.info("workflow_completed", session_id=session_id, duration_ms=duration_ms)
        return cast(AgentState, final_state)
    except Exception as e:
        logger.error(
            "workflow_failed",
            session_id=session_id,
            error=str(e),
            exc_info=True,
        )
        raise
