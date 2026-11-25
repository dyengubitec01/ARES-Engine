"""
Tool Executor 노드 - 도구 실행.

Story 2.8 AC 2.8.4: Tool Client를 호출하여 도구를 실행하고 결과를 context에 추가.
"""

import structlog
from langchain_core.runnables import RunnableConfig

from app.clients import get_tool_client
from app.core.exceptions import BusinessException
from app.workflows.main_agent.state import AgentState
from app.workflows.shared.tracing_utils import extract_trace_context

logger = structlog.get_logger()


async def tool_executor(state: AgentState, config: RunnableConfig) -> dict:
    """
    도구 실행 노드.

    Tool Client를 사용하여 도구를 실행하고 결과를 context에 추가한다.

    AC 2.8.4: Tool Client 호출, 결과를 context 형식으로 변환
    AC 2.8.10: RunnableConfig에서 trace_id 추출 (향후 실제 서버 연동 시 사용)

    Args:
        state: 현재 워크플로우 상태.
        config: LangGraph에서 전달받은 RunnableConfig.

    Returns:
        업데이트할 상태 필드:
        - context: 도구 실행 결과 (포맷팅됨)
        - thoughts: 추론 과정 추가
    """
    standalone_query = state.get("standalone_query") or state["query"]
    trace_ctx = extract_trace_context(config)

    try:
        tool_client = get_tool_client()

        # 1. 도구 목록 조회
        tools = await tool_client.list_tools(
            trace_id=trace_ctx.trace_id,
            observation_id=trace_ctx.observation_id,
        )
        if not tools:
            logger.info("tool_executor_no_tools")
            return {
                "context": [],
                "thoughts": ["사용 가능한 도구가 없습니다."],
            }

        # 2. 단순 매칭으로 적합한 도구 선택 (Story 2.8: 단순 매칭, Epic 3: LLM 기반)
        selected_tool = _select_tool(tools, standalone_query)
        tool_name = selected_tool.name

        # 3. 도구 실행
        arguments = _build_arguments(tool_name, standalone_query, state)
        result = await tool_client.call_tool(
            tool_name,
            arguments,
            trace_id=trace_ctx.trace_id,
            observation_id=trace_ctx.observation_id,
        )

        if result.success:
            context_entry = f"[도구 결과: {tool_name}] {result.result}"
            thought = f"도구({tool_name})를 실행하여 결과를 얻었습니다."
            logger.info("tool_execution_completed", tool_name=tool_name)
        else:
            context_entry = f"[도구 오류: {tool_name}] {result.error}"
            thought = f"도구({tool_name}) 실행 중 오류가 발생했습니다."
            logger.warning("tool_execution_error_response", tool_name=tool_name, error=result.error)

        return {
            "context": [context_entry],
            "thoughts": [thought],
        }

    except BusinessException as e:
        logger.warning("tool_executor_failed", error=str(e))
        return {
            "context": ["[도구 오류] 도구 실행에 실패했습니다. 사용자에게 도구 실행 중 오류가 발생했음을 안내해 주세요."],
            "thoughts": ["도구 실행에 실패했습니다."],
        }

    except Exception as e:
        logger.error("tool_executor_unexpected_error", error=str(e), exc_info=True)
        return {
            "context": ["[도구 오류] 도구 실행에 실패했습니다. 사용자에게 도구 실행 중 오류가 발생했음을 안내해 주세요."],
            "thoughts": ["도구 실행에 실패했습니다."],
        }


def _select_tool(tools, query: str):
    """질문에 적합한 도구를 단순 매칭으로 선택한다.

    Args:
        tools: 사용 가능한 도구 목록.
        query: 사용자 질문.

    Returns:
        선택된 ToolDefinition. 매칭 실패 시 첫 번째 도구 반환.
    """
    query_lower = query.lower()
    for tool in tools:
        # 도구 이름이나 설명에 매칭되는 키워드 검색
        if tool.name.lower() in query_lower or tool.description.lower() in query_lower:
            return tool
    # 매칭 실패 시 첫 번째 도구
    return tools[0]


def _build_arguments(tool_name: str, query: str, state: AgentState | None = None) -> dict:
    """도구 실행에 필요한 인자를 구성한다.

    Args:
        tool_name: 도구 이름.
        query: 사용자 질문.
        state: 워크플로우 상태 (history 등 전달용).

    Returns:
        도구에 전달할 인자 딕셔너리.
    """
    # 실제 Tool 서버 도구
    if tool_name == "summary":
        history = state.get("history", []) if state else []
        return {"history": history, "summary": None}
    # Mock 환경에서의 기본 인자 매핑
    if tool_name == "get_weather":
        return {"location": _extract_location(query)}
    if tool_name == "calculate":
        return {"expression": query}
    return {"query": query}


def _extract_location(query: str) -> str:
    """질문에서 위치 정보를 추출한다.

    Args:
        query: 사용자 질문.

    Returns:
        추출된 위치. 기본값 "서울".
    """
    locations = ["서울", "부산", "제주", "뉴욕"]
    for loc in locations:
        if loc in query:
            return loc
    return "서울"
