"""
Rewriter 노드 - 질문 재구성.

Story 2.2: LLM 기반 Query Rewriting 로직 구현.

대화 이력(history)을 참조하여 사용자의 질문(query)을
문맥에 독립적인 질문(standalone_query)으로 변환한다.
"""

import structlog

from app.core.config import settings
from app.core.exceptions import BusinessException
from app.core.llm_factory import llm_factory
from app.workflows.main_agent.prompts.rewriter import get_rewriter_prompt
from app.workflows.main_agent.state import AgentState

logger = structlog.get_logger()


def format_history_for_prompt(history: list[dict]) -> str:
    """
    대화 이력을 프롬프트용 문자열로 변환.

    Args:
        history: 대화 이력 리스트. 각 항목은 {"role": str, "content": str} 형태.

    Returns:
        포맷된 문자열. 빈 리스트인 경우 "(이전 대화 없음)" 반환.
    """
    if not history:
        return "(이전 대화 없음)"

    lines = []
    for msg in history:
        role_tag = "user" if msg["role"] == "user" else "assistant"
        lines.append(f"<{role_tag}>{msg['content']}</{role_tag}>")

    return "\n".join(lines)


async def rewriter(state: AgentState) -> dict:
    """
    질문 재구성 노드.

    대화 이력을 분석하여 모호한 참조("그것", "이전에 말한 것" 등)를
    구체적인 내용으로 대체한 standalone_query를 생성한다.

    AC 2.2.3: 이력이 없으면 LLM 호출 없이 원본 질문 반환.
    AC 2.2.4: 이력이 있으면 invoke_with_failover() 사용.
    AC 2.2.5: standalone_query와 thoughts만 반환.
    AC 2.2.6: 빈 응답 시 원본 query fallback.
    AC 2.2.7: 적절한 thoughts 메시지 추가.

    Args:
        state: 현재 워크플로우 상태.

    Returns:
        업데이트할 상태 필드:
        - standalone_query: 재구성된 질문
        - thoughts: 추론 과정 추가
    """
    query = state["query"]
    history = state.get("history", [])
    session_id = state["session_id"]

    # SKIP_REWRITER 플래그가 True면 질문 재구성 건너뛰기
    if settings.SKIP_REWRITER:
        logger.info("node_skipped", node="rewriter", reason="SKIP_REWRITER=true")
        return {
            "standalone_query": query,
            "thoughts": ["질문 재구성을 건너뛰었습니다."],
        }

    # AC 2.2.3: 이력이 없으면 LLM 호출 없이 원본 질문 반환
    if not history:
        return {
            "standalone_query": query,
            "thoughts": ["대화 이력이 없어 원본 질문을 그대로 사용합니다."],
        }

    # AC 2.2.4: 이력이 있으면 LLM 호출
    try:
        formatted_history = format_history_for_prompt(history)
        rewriter_prompt = get_rewriter_prompt()

        # AC 3.8.2: chain 패턴으로 LangFuse Prompt-Generation 자동 연결
        response = await llm_factory.invoke_chain_with_failover(
            role="primary",
            prompt=rewriter_prompt,
            input_dict={"history": formatted_history, "query": query},
            session_id=session_id,
            request_type="query_rewrite",
            trace_metadata={"original_query": query},
        )

        # AC 2.2.6: 출력 파싱 - 빈 응답 시 원본 query fallback
        # response.content는 str | list[str | dict] 일 수 있음 (multimodal 응답)
        content = response.content
        if isinstance(content, str):
            standalone_query = content.strip() or query
        elif isinstance(content, list) and content:
            # list인 경우 첫 번째 str 요소 사용
            first_item = content[0]
            if isinstance(first_item, str):
                standalone_query = first_item.strip() or query
            elif isinstance(first_item, dict) and "text" in first_item:
                standalone_query = str(first_item["text"]).strip() or query
            else:
                standalone_query = query
        else:
            standalone_query = query

        # AC 2.2.7: 성공 시 thoughts 메시지
        thought = "대화 맥락을 반영하여 질문을 명확히 했습니다."

    except BusinessException as e:
        # AC 2.2.4: Failover 실패 시 원본 query fallback (워크플로우 계속 진행)
        logger.warning("rewriter_llm_failed", error=str(e))
        standalone_query = query
        thought = "대화 맥락을 반영하여 질문을 명확히 했습니다."

    except Exception as e:
        # 예상치 못한 오류도 graceful하게 처리
        logger.error("rewriter_unexpected_error", error=str(e), exc_info=True)
        standalone_query = query
        thought = "대화 맥락을 반영하여 질문을 명확히 했습니다."

    return {
        "standalone_query": standalone_query,
        "thoughts": [thought],
    }
