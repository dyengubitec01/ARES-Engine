"""
Synthesizer 노드 - 답변 생성.

Story 2.5: LLM 기반 답변 생성 로직 구현.
Story 2.6: astream_events 호환 스트리밍 LLM 호출.

검색된 context와 재구성된 질문(standalone_query)을 기반으로
최종 응답(response)을 생성한다.

Note: astream_events가 LLM 스트리밍 이벤트를 캡처하려면
노드가 RunnableConfig를 받아서 LLM 호출에 전달해야 함.
"""

from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig

from app.core.config import settings
from app.core.exceptions import BusinessException
from app.core.llm_factory import llm_factory
from app.workflows.main_agent.nodes.rewriter import format_history_for_prompt
from app.workflows.main_agent.prompts.synthesizer import (
    NO_CONTEXT_RESPONSE,
    get_synthesizer_no_rag_prompt,
    get_synthesizer_prompt,
)
from app.workflows.main_agent.state import AgentState

logger = structlog.get_logger()


async def synthesizer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """
    답변 생성 노드 (스트리밍).

    검색된 context와 재구성된 질문(standalone_query)을 기반으로
    최종 응답(response)을 생성한다.

    AC 2.5.4: 컨텍스트 기반 자연스러운 답변 생성
    AC 2.5.7: "primary" 역할 모델 사용, LangFuse 트레이스
    AC 2.6.4: 스트리밍 LLM 호출 (토큰 단위 SSE)

    Note:
        RunnableConfig를 LLM 호출에 전달하여 astream_events가
        on_chat_model_stream 이벤트를 캡처할 수 있게 함.

    Args:
        state: 현재 워크플로우 상태.
        config: LangGraph에서 전달받은 RunnableConfig (callbacks 포함).

    Returns:
        업데이트할 상태 필드:
        - response: 생성된 답변
        - thoughts: 추론 과정 추가
    """
    standalone_query = state.get("standalone_query", state["query"])
    context = state.get("context", [])
    history = state.get("history", [])
    session_id = state["session_id"]

    # 대화 이력 포맷팅
    formatted_history = format_history_for_prompt(history)

    # AC 2.5.7, AC 2.6.4: 스트리밍 LLM 호출 (primary 역할)
    route = state.get("route", "rag")

    try:
        # AC 3.8.1: chain 패턴으로 LangFuse Prompt-Generation 자동 연결
        if settings.SKIP_RAG or route == "direct" or not context:
            # Path A: context 없이 LLM 직접 응답
            synth_prompt = get_synthesizer_no_rag_prompt()
            input_dict: dict[str, str] = {
                "history": formatted_history,
                "query": standalone_query,
            }
        else:
            # Path B: RAG context 기반 응답
            synth_prompt = get_synthesizer_prompt()
            input_dict = {
                "history": formatted_history,
                "context": "\n".join(context),
                "query": standalone_query,
            }

        # chain 패턴: PromptTemplate.metadata의 langfuse_prompt가 자동 전파
        llm = llm_factory.get_llm("primary")
        chain = synth_prompt | llm
        collected_tokens: list[str] = []

        async for chunk in chain.astream(input_dict, config=config):
            if chunk.content:
                collected_tokens.append(chunk.content)

        answer = "".join(collected_tokens).strip() or NO_CONTEXT_RESPONSE
        # LLM이 대화 이력의 "AI: " 패턴을 모방하여 응답을 시작하는 경우 제거
        while answer.startswith("AI: "):
            answer = answer[4:]

        if settings.SKIP_RAG or route == "direct" or not context:
            thought = "LLM이 직접 답변을 생성했습니다."
        else:
            thought = f"검색된 {len(context)}개 문서를 기반으로 답변을 생성했습니다."
        logger.info("synthesizer_completed", session_id=session_id)

    except BusinessException as e:
        logger.warning("synthesizer_llm_failed", error=str(e))
        answer = "답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        thought = "답변 생성 중 오류가 발생했습니다."

    except Exception as e:
        logger.error("synthesizer_unexpected_error", error=str(e), exc_info=True)
        answer = "답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        thought = "답변 생성 중 오류가 발생했습니다."

    return {
        "response": answer,
        "thoughts": [thought],
    }
