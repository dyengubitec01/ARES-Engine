"""
Intent Router 노드 - 질문 의도 분류.

Story 2.8 AC 2.8.1: LLM 기반 의도 분류로 실행 경로(rag/tool/both) 결정.
Story 3.2.2 AC 3.2.2.4~7: 2단계 판단 + SKIP 플래그 경로 제한 + direct 경로.
"""

import structlog

from app.core.exceptions import BusinessException
from app.core.llm_factory import llm_factory
from app.workflows.main_agent.prompts.router import (
    build_router_prompt,
    get_available_routes,
)
from app.workflows.main_agent.state import AgentState

logger = structlog.get_logger()

VALID_ROUTES = ("both", "tool", "rag", "direct")  # 매칭 우선순위: both > tool > rag > direct


def _get_default_route(available_routes: list[str]) -> str:
    """가용 경로 중 기본 경로를 반환한다."""
    if "rag" in available_routes:
        return "rag"
    if "tool" in available_routes:
        return "tool"
    return "direct"


def _parse_route(content: str, available_routes: list[str]) -> str:
    """LLM 응답에서 route 값을 파싱한다.

    Args:
        content: LLM 응답 문자열.
        available_routes: 사용 가능한 경로 목록.

    Returns:
        파싱된 route 값. 유효하지 않거나 가용하지 않으면 기본값.
    """
    default_route = _get_default_route(available_routes)
    cleaned = content.strip().lower()

    if cleaned in VALID_ROUTES:
        return cleaned if cleaned in available_routes else default_route

    # 응답에 route 값이 포함되어 있는 경우 추출
    for route in VALID_ROUTES:
        if route in cleaned:
            return route if route in available_routes else default_route
    return default_route


async def router(state: AgentState) -> dict:
    """
    Intent Router 노드.

    standalone_query를 LLM에 전달하여 실행 경로를 결정한다.
    SKIP_RAG / SKIP_TOOL 플래그에 따라 가용 경로를 동적으로 제한한다.

    Args:
        state: 현재 워크플로우 상태.

    Returns:
        업데이트할 상태 필드:
        - route: 결정된 실행 경로 ("rag" | "tool" | "both" | "direct")
        - thoughts: 추론 과정 추가
    """
    standalone_query = state.get("standalone_query") or state["query"]
    session_id = state["session_id"]

    available_routes = get_available_routes()
    default_route = _get_default_route(available_routes)

    # 가용 경로가 1개 이하인 경우 LLM 호출 불필요
    if len(available_routes) <= 1:
        fallback = available_routes[0] if available_routes else "rag"
        logger.info("router_single_route", route=fallback, available=available_routes)
        return {
            "route": fallback,
            "thoughts": [f"가용 경로가 제한되어 {fallback} 경로로 진행합니다."],
        }

    route_descriptions = {
        "rag": "RAG 경로",
        "tool": "Tool 경로",
        "both": "RAG + Tool 병렬 경로",
        "direct": "Direct 경로 (LLM 직접 응답)",
    }

    try:
        router_prompt = build_router_prompt(available_routes)

        # AC 3.8.3: chain 패턴으로 LangFuse Prompt-Generation 자동 연결
        response = await llm_factory.invoke_chain_with_failover(
            role="fast",
            prompt=router_prompt,
            input_dict={"query": standalone_query},
            session_id=session_id,
            request_type="intent_routing",
            trace_metadata={"query": standalone_query},
        )

        content = response.content
        if isinstance(content, str):
            route = _parse_route(content, available_routes)
        elif isinstance(content, list) and content:
            first_item = content[0]
            if isinstance(first_item, str):
                route = _parse_route(first_item, available_routes)
            elif isinstance(first_item, dict) and "text" in first_item:
                route = _parse_route(str(first_item["text"]), available_routes)
            else:
                route = default_route
        else:
            route = default_route

        thought = f"질문 의도를 분석하여 {route_descriptions[route]}를 선택했습니다."
        logger.info(
            "router_decided",
            route=route,
            available=available_routes,
            query_preview=standalone_query[:100],
        )

    except BusinessException as e:
        logger.warning("router_llm_failed", default_route=default_route, error=str(e))
        route = default_route
        thought = f"질문 의도를 분석하여 {route_descriptions[default_route]}를 선택했습니다."

    except Exception as e:
        logger.error("router_unexpected_error", error=str(e), exc_info=True)
        route = default_route
        thought = f"질문 의도를 분석하여 {route_descriptions[default_route]}를 선택했습니다."

    return {
        "route": route,
        "thoughts": [thought],
    }
