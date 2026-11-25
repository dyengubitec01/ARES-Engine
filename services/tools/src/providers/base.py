"""LLM Provider 추상 베이스 클래스.

모든 LLM Provider는 이 ABC를 상속받아 구현한다.
에이전트 서버(LLMFactory) 패턴 적용 — invoke() + invoke_with_failover().
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """LLM Provider 추상 인터페이스.

    모든 I/O는 async/await 기반.
    role 파라미터로 models.yaml 역할 매핑 — 코드에 모델명 없음.
    messages: OpenAI 포맷 list[dict[str, str]] — LangChain 타입 미사용.
    반환: dict[str, Any] — OpenAI 응답 그대로, 별도 래핑 없음.
    """

    @abstractmethod
    async def invoke(
        self,
        role: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        """단건 LLM 호출.

        Args:
            role: models.yaml 역할명 (예: "primary", "fast", "reasoning").
            messages: OpenAI 포맷 메시지 리스트.

        Returns:
            OpenAI 응답 dict 그대로.
        """
        ...

    @abstractmethod
    async def invoke_with_failover(
        self,
        role: str,
        messages: list[dict[str, str]],
        max_retries: int = 1,
        *,
        trace_metadata: dict[str, Any] | None = None,
        trace_context: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Failover 체인 자동 순회 포함 호출.

        Args:
            role: models.yaml 역할명.
            messages: OpenAI 포맷 메시지 리스트.
            max_retries: 각 모델당 최대 재시도 횟수.
            trace_metadata: Langfuse 트레이싱용 메타데이터.
            trace_context: Langfuse trace 연결 정보 (cross-service).

        Returns:
            OpenAI 응답 dict 그대로.
        """
        ...
