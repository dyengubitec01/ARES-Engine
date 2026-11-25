"""요약 비즈니스 로직.

프롬프트 템플릿 엔진으로 시스템 프롬프트를 구성하고,
Provider를 호출하여 LLM 요약 결과를 반환한다.
"""

import logging
from typing import Any

from src.providers.base import BaseLLMProvider
from src.schemas.summary import ChatMessage
from src.services.prompt_engine import render_system_prompt

logger = logging.getLogger(__name__)


async def summarize(
    history: list[ChatMessage],
    provider: BaseLLMProvider,
    *,
    summary: str | None = None,
    trace_metadata: dict[str, Any] | None = None,
    trace_context: dict[str, str] | None = None,
) -> str:
    """대화 이력 기반 요약 실행.

    1. render_system_prompt("summary")로 시스템 프롬프트 생성
    2. 이전 요약이 있으면 컨텍스트로 포함
    3. history 메시지를 순서대로 추가
    4. Provider.invoke_with_failover()로 LLM 호출

    Args:
        history: 대화 이력 (ChatMessage 리스트).
        provider: LLM Provider 인스턴스.
        summary: 이전 요약 텍스트 (갱신 시 전달).
        trace_metadata: Langfuse 트레이싱용 메타데이터.
        trace_context: Langfuse trace 연결 정보 (cross-service).

    Returns:
        요약된 텍스트.
    """
    system_prompt = render_system_prompt("summary")

    # history를 텍스트로 변환 (role별로 쪼개면 LLM이 대화를 이어가려 함)
    history_text = "\n".join(
        f"{msg.role}: {msg.content}" for msg in history
    )

    user_content = f"[대화 내용]\n{history_text}"
    if summary:
        user_content = f"[이전 요약]\n{summary}\n\n{user_content}"

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    total_chars = sum(len(m.content) for m in history)
    logger.info("요약 요청: history_count=%d, total_chars=%d", len(history), total_chars)

    response = await provider.invoke_with_failover(
        role="primary",
        messages=messages,
        trace_metadata=trace_metadata,
        trace_context=trace_context,
    )

    content = response["choices"][0]["message"]["content"]

    logger.info("요약 완료: result_length=%d", len(content))
    return content
