"""Gateway LLM Provider 구현.

OpenAI Compatible Gateway에 httpx로 직접 호출한다.
LangChain/LangGraph 미사용 (TECH_SPEC 1.3).
"""

import logging
from typing import Any

import httpx

from src.config.loader import get_config_value
from src.config.models import get_fallback_chain, get_model_for_role, load_models_config
from src.config.settings import get_settings
from src.exceptions.exceptions import LLMProviderError
from src.middleware.langfuse import create_span
from src.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class GatewayLLMProvider(BaseLLMProvider):
    """OpenAI Compatible Gateway LLM Provider.

    httpx.AsyncClient로 Gateway 직접 호출.
    Authorization: Bearer {LLM_API_KEY} 헤더.
    LLM 파라미터(max_tokens, temperature)는 config.yaml에서 관리.
    """

    def __init__(
        self,
        gateway_url: str,
        api_key: str,
        max_tokens: int,
        temperature: float,
        default_timeout: float,
        connect_timeout: float | None = None,
    ) -> None:
        """Provider 초기화.

        Args:
            gateway_url: Gateway base URL (예: "http://localhost:4000/v1").
            api_key: Gateway 인증 API Key.
            max_tokens: LLM 최대 토큰 수.
            temperature: LLM temperature.
            default_timeout: HTTP 요청 타임아웃(초).
            connect_timeout: TCP 연결 타임아웃(초). None이면 default_timeout 사용.
        """
        self._gateway_url = gateway_url.rstrip("/")
        self._api_key = api_key
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._default_timeout = default_timeout
        self._connect_timeout = connect_timeout
        self._client: httpx.AsyncClient | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        """AsyncClient 인스턴스 반환. 없거나 닫혀 있으면 새로 생성."""
        if self._client is None or self._client.is_closed:
            if self._connect_timeout is not None:
                timeout = httpx.Timeout(
                    self._default_timeout,
                    connect=self._connect_timeout,
                )
            else:
                timeout = self._default_timeout
            self._client = httpx.AsyncClient(
                headers=self._build_headers(),
                timeout=timeout,
            )
        return self._client

    async def close(self) -> None:
        """HTTP 클라이언트 리소스 정리."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    def _build_headers(self) -> dict[str, str]:
        """HTTP 요청 헤더 생성."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def _build_payload(
        self,
        model: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        """LLM 요청 페이로드 생성."""
        return {
            "model": model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }

    async def invoke(
        self,
        role: str,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        """단건 LLM 호출.

        role → models.yaml 모델명 조회 → httpx POST → 응답 반환.

        Args:
            role: models.yaml 역할명.
            messages: OpenAI 포맷 메시지 리스트.

        Returns:
            OpenAI 응답 dict 그대로.

        Raises:
            httpx.HTTPStatusError: Gateway가 4xx/5xx 응답 시.
            httpx.TimeoutException: 요청 타임아웃 시.
        """
        model = get_model_for_role(role)
        if not model:
            raise ValueError(f"역할 '{role}'에 매핑된 모델이 없습니다.")

        url = f"{self._gateway_url}/chat/completions"
        payload = self._build_payload(model, messages)

        logger.info(
            "LLM 호출: role=%s, model=%s, url=%s",
            role, model, url,
        )

        try:
            response = await self._ensure_client().post(
                url,
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "LLM HTTP 에러: role=%s, model=%s, status=%d",
                role, model, exc.response.status_code,
            )
            raise
        except httpx.TimeoutException:
            logger.error(
                "LLM 타임아웃: role=%s, model=%s, url=%s",
                role, model, url,
            )
            raise

    async def invoke_with_failover(
        self,
        role: str,
        messages: list[dict[str, str]],
        max_retries: int = 1,
        *,
        trace_metadata: dict[str, Any] | None = None,
        trace_context: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Failover 체인을 따라 LLM 호출.

        get_fallback_chain(role)으로 체인을 조회한 뒤 순차 시도.
        각 역할마다 max_retries만큼 재시도하고, 모두 실패하면 다음 역할로 전환.
        모든 체인이 소진되면 RuntimeError를 raise한다.
        (fallback_message 반환은 Story 2-3 Graceful Degradation 범위)

        4xx 에러(429 제외)는 클라이언트 측 문제이므로 failover 없이 즉시 전파.
        5xx, 429, 타임아웃, 연결 실패만 failover 대상.

        Args:
            role: models.yaml 역할명.
            messages: OpenAI 포맷 메시지 리스트.
            max_retries: 각 역할당 최대 재시도 횟수.
            trace_metadata: Langfuse 트레이싱용 메타데이터.
            trace_context: Langfuse trace 연결 정보 (cross-service).

        Returns:
            OpenAI 응답 dict 그대로.

        Raises:
            LLMProviderError: 모든 fallback 체인 소진 시 (Graceful Degradation).
            httpx.HTTPStatusError: 4xx 에러 시 (429 제외).
        """
        chain = get_fallback_chain(role)
        if not chain:
            raise ValueError(f"역할 '{role}'의 fallback 체인이 비어 있습니다.")

        last_exception: Exception | None = None

        for idx, current_role in enumerate(chain):
            is_fallback = idx > 0
            for attempt in range(1, max_retries + 1):
                span = create_span(
                    name=f"llm-invoke:{current_role}",
                    input_data={
                        "role": current_role,
                        "original_role": role,
                        "is_fallback": is_fallback,
                        "attempt": attempt,
                        "chain_index": idx,
                    },
                    metadata=trace_metadata,
                    trace_context=trace_context,
                )
                try:
                    result = await self.invoke(current_role, messages)
                    if span:
                        content = (
                            result.get("choices", [{}])[0]
                            .get("message", {})
                            .get("content", "")
                        )
                        span.update(output=content)
                        span.end()
                    if is_fallback:
                        logger.info(
                            "Failover 성공: %s → %s (시도 %d/%d)",
                            role, current_role, attempt, max_retries,
                        )
                    return result
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status < 500 and status != 429:
                        if span:
                            span.update(
                                output={"status": "error", "error": str(exc)},
                                level="ERROR",
                            )
                            span.end()
                        raise
                    last_exception = exc
                    if span:
                        span.update(
                            output={"status": "error", "error": str(exc)},
                            level="ERROR",
                        )
                        span.end()
                    logger.warning(
                        "LLM 호출 실패: role=%s, 시도=%d/%d, status=%d",
                        current_role, attempt, max_retries, status,
                    )
                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    last_exception = exc
                    if span:
                        span.update(
                            output={"status": "error", "error": str(exc)},
                            level="ERROR",
                        )
                        span.end()
                    logger.warning(
                        "LLM 호출 실패: role=%s, 시도=%d/%d, 에러=%s",
                        current_role, attempt, max_retries, exc,
                    )

        fallback_message = load_models_config().fallback_message
        raise LLMProviderError(
            detail=fallback_message,
            role=role,
            chain=chain,
        ) from last_exception


def create_gateway_provider() -> GatewayLLMProvider:
    """설정값을 읽어 GatewayLLMProvider 인스턴스 생성.

    Returns:
        초기화된 GatewayLLMProvider 인스턴스.
    """
    settings = get_settings()
    return GatewayLLMProvider(
        gateway_url=settings.llm_gateway_url,
        api_key=settings.llm_api_key,
        max_tokens=get_config_value("llm.max_tokens", 512),
        temperature=get_config_value("llm.temperature", 0.4),
        default_timeout=get_config_value("llm.default_timeout", 30),
        connect_timeout=get_config_value("llm.connect_timeout", 10),
    )
