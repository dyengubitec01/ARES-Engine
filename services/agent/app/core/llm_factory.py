"""
LLM Proxy (Factory) with Failover & Routing.

LLM Proxy - Failover & Routing 로직 집약 (DESIGN_SPEC.md Section 2.2)
Role-Based Routing + Configurable Failover + Graceful Degradation
LangFuse Tracing 통합 (Story 1.5)
"""

from collections.abc import AsyncIterator
from typing import Any

import httpx
import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import ModelConfig, get_model_config
from app.core.enums import ErrorCode
from app.core.exceptions import BusinessException
from app.core.tracing import tracing

logger = structlog.get_logger()

# Failover를 트리거하는 예외 타입
FAILOVER_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.TimeoutException,
)


class LLMFactory:
    """LLM Factory with role-based routing and failover support."""

    def __init__(self, config: ModelConfig | None = None) -> None:
        self._config = config
        self._llm_cache: dict[str, BaseChatModel] = {}

    @property
    def config(self) -> ModelConfig:
        """Get model configuration (lazy loading)."""
        if self._config is None:
            self._config = get_model_config()
        return self._config

    def get_model_for_role(self, role: str) -> str | None:
        """Get model name for a given role."""
        return self.config.get_model_for_role(role)

    def get_fallback_role(self, role: str) -> str | None:
        """Get fallback role for a given role."""
        return self.config.get_fallback_role(role)

    def get_base_url(self, role: str) -> str | None:
        """Get LLM base URL for a given role."""
        return self.config.get_server_url(role)

    def get_model_with_fallback(self, role: str) -> tuple[str, str] | None:
        """
        Get model and URL for role, following fallback chain if needed.

        Returns:
            Tuple of (model_name, base_url) or None if no model available.
        """
        current_role = role
        visited: set[str] = set()

        while current_role and current_role not in visited:
            visited.add(current_role)

            model = self.get_model_for_role(current_role)
            url = self.get_base_url(current_role)

            if model and url:
                return (model, url)

            # Try fallback
            current_role = self.get_fallback_role(current_role)

        return None

    @property
    def fallback_message(self) -> str:
        """Get graceful degradation message."""
        return self.config.fallback_message

    def _get_available_roles(self) -> list[str]:
        """Get list of available role names."""
        return list(self.config.roles.keys())

    def get_llm(self, role: str) -> BaseChatModel:
        """
        Get LLM instance for a given role (cached).

        Args:
            role: Role name (e.g., "primary", "fast", "reasoning")

        Returns:
            ChatOpenAI instance configured for the role.

        Raises:
            ValueError: If role doesn't exist in configuration.
        """
        # Check cache first
        if role in self._llm_cache:
            return self._llm_cache[role]

        # Validate role exists
        model_info = self.get_model_with_fallback(role)
        if model_info is None:
            available = self._get_available_roles()
            raise ValueError(
                f"Unknown role: '{role}'. Available roles: {available}"
            )

        model_name, base_url = model_info

        # Create and cache LLM instance (settings에서 LLM 클라이언트 설정 가져옴)
        from app.core.config import settings as app_settings

        llm = ChatOpenAI(
            base_url=base_url,
            model=model_name,
            api_key=app_settings.LLM_API_KEY,
            timeout=app_settings.LLM_TIMEOUT,
            max_tokens=app_settings.LLM_MAX_TOKENS,
            temperature=app_settings.LLM_TEMPERATURE,
            stream_usage=True,
        )
        self._llm_cache[role] = llm

        return llm


    def _prepare_tracing_config(
        self,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        request_type: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        트레이싱 설정을 준비하는 헬퍼 메서드.

        Args:
            session_id: Session ID for LangFuse tracing (AC 1.5.4).
            user_id: User ID for LangFuse tracing (AC 1.5.4).
            request_type: Request type for metadata (e.g., "chat", "planning").
            trace_metadata: Additional metadata for LangFuse tracing.

        Returns:
            LangFuse config dict for chain invocation.
        """
        try:
            # trace_metadata에 request_type 포함
            full_metadata = trace_metadata.copy() if trace_metadata else {}
            if request_type:
                full_metadata["request_type"] = request_type

            return tracing.get_langfuse_config(
                session_id=session_id,
                user_id=user_id,
                metadata=full_metadata if full_metadata else None,
            )
        except Exception as e:
            logger.warning("tracing_config_failed", error=str(e))
            return {}

    async def invoke(
        self, role: str, messages: list[BaseMessage]
    ) -> AIMessage:
        """
        Invoke LLM with messages asynchronously.

        Args:
            role: Role name for model selection.
            messages: List of messages to send.

        Returns:
            AIMessage response from LLM.

        Raises:
            BusinessException: With ErrorCode.LLM_CONNECTION if server is unreachable.
            BusinessException: With ErrorCode.LLM_RESPONSE if response processing fails.
        """
        try:
            llm = self.get_llm(role)
            response = await llm.ainvoke(messages)
            return response  # type: ignore[return-value]
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise BusinessException(
                ErrorCode.LLM_CONNECTION, detail=f"LLM 서버({role}) 연결 실패: {e}"
            ) from e
        except ValueError:
            raise  # get_llm의 ValueError는 그대로 전파
        except Exception as e:
            raise BusinessException(
                ErrorCode.LLM_RESPONSE, detail=f"LLM 응답 처리 오류({role}): {e}"
            ) from e

    async def stream(
        self, role: str, messages: list[BaseMessage]
    ) -> AsyncIterator[AIMessageChunk]:
        """
        Stream LLM response asynchronously.

        Args:
            role: Role name for model selection.
            messages: List of messages to send.

        Yields:
            AIMessageChunk for each streamed chunk.

        Raises:
            BusinessException: With ErrorCode.LLM_CONNECTION if server is unreachable.
            BusinessException: With ErrorCode.LLM_RESPONSE if response processing fails.
        """
        try:
            llm = self.get_llm(role)
            async for chunk in llm.astream(messages):
                yield chunk  # type: ignore[misc]
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise BusinessException(
                ErrorCode.LLM_CONNECTION, detail=f"LLM 서버({role}) 연결 실패: {e}"
            ) from e
        except ValueError:
            raise  # get_llm의 ValueError는 그대로 전파
        except Exception as e:
            raise BusinessException(
                ErrorCode.LLM_RESPONSE, detail=f"LLM 응답 처리 오류({role}): {e}"
            ) from e

    async def invoke_with_failover(
        self,
        role: str,
        messages: list[BaseMessage],
        max_retries: int = 1,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        request_type: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> AIMessage:
        """
        Invoke LLM with automatic failover on connection errors (AC 1.5.2).

        Args:
            role: Initial role name for model selection.
            messages: List of messages to send.
            max_retries: Maximum retries per role before failover (default: 1).
            session_id: Session ID for LangFuse tracing (AC 1.5.4).
            user_id: User ID for LangFuse tracing (AC 1.5.4).
            request_type: Request type for metadata (e.g., "chat", "planning").
            trace_metadata: Additional metadata for LangFuse tracing.

        Returns:
            AIMessage response from LLM.

        Raises:
            BusinessException: With ErrorCode.ALL_SERVERS_DOWN if all servers fail.
            ValueError: If initial role doesn't exist.
        """
        langfuse_config = self._prepare_tracing_config(
            session_id=session_id,
            user_id=user_id,
            request_type=request_type,
            trace_metadata=trace_metadata,
        )

        current_role = role
        visited: set[str] = set()

        while current_role and current_role not in visited:
            visited.add(current_role)
            model_name = self.get_model_for_role(current_role)

            for attempt in range(max_retries + 1):
                try:
                    llm = self.get_llm(current_role)
                    response = await llm.ainvoke(messages, config=langfuse_config)
                    return response  # type: ignore[return-value]
                except FAILOVER_EXCEPTIONS as e:
                    if attempt < max_retries:
                        logger.warning(
                            "llm_retry",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            role=current_role,
                            error=type(e).__name__,
                        )
                        continue

                    # 재시도 소진, fallback으로 전환
                    fallback_role = self.get_fallback_role(current_role)
                    if fallback_role:
                        fallback_model = self.get_model_for_role(fallback_role)
                        logger.warning(
                            "llm_failover_triggered",
                            from_role=current_role,
                            from_model=model_name,
                            to_role=fallback_role,
                            to_model=fallback_model,
                            reason=type(e).__name__,
                        )
                        current_role = fallback_role
                        break
                    else:
                        # Graceful Degradation
                        logger.error(
                            "llm_all_attempts_failed",
                            role=current_role,
                            model=model_name,
                            error=type(e).__name__,
                        )
                        raise BusinessException(
                            ErrorCode.ALL_SERVERS_DOWN, detail=self.fallback_message
                        ) from e
                except ValueError:
                    raise  # 존재하지 않는 역할은 그대로 전파

        # fallback 체인 끝까지 도달
        raise BusinessException(ErrorCode.ALL_SERVERS_DOWN, detail=self.fallback_message)

    async def invoke_chain_with_failover(
        self,
        role: str,
        prompt: ChatPromptTemplate,
        input_dict: dict[str, Any],
        max_retries: int = 1,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        request_type: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> AIMessage:
        """
        Invoke prompt|llm chain with automatic failover (AC 3.8.2, 3.8.3).

        chain 패턴을 사용하여 LangFuse Prompt-Generation 연결을 자동화한다.
        PromptTemplate.metadata의 langfuse_prompt가 chain을 통해 자동 전파된다.

        Args:
            role: Initial role name for model selection.
            prompt: ChatPromptTemplate (with optional langfuse_prompt metadata).
            input_dict: Template variables (e.g. {"history": ..., "query": ...}).
            max_retries: Maximum retries per role before failover (default: 1).
            session_id: Session ID for LangFuse tracing.
            user_id: User ID for LangFuse tracing.
            request_type: Request type for metadata.
            trace_metadata: Additional metadata for LangFuse tracing.

        Returns:
            AIMessage response from LLM.

        Raises:
            BusinessException: With ErrorCode.ALL_SERVERS_DOWN if all servers fail.
            ValueError: If initial role doesn't exist.
        """
        langfuse_config = self._prepare_tracing_config(
            session_id=session_id,
            user_id=user_id,
            request_type=request_type,
            trace_metadata=trace_metadata,
        )

        current_role = role
        visited: set[str] = set()

        while current_role and current_role not in visited:
            visited.add(current_role)
            model_name = self.get_model_for_role(current_role)

            for attempt in range(max_retries + 1):
                try:
                    llm = self.get_llm(current_role)
                    chain = prompt | llm
                    response = await chain.ainvoke(input_dict, config=langfuse_config)
                    return response  # type: ignore[return-value]
                except FAILOVER_EXCEPTIONS as e:
                    if attempt < max_retries:
                        logger.warning(
                            "llm_chain_retry",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            role=current_role,
                            error=type(e).__name__,
                        )
                        continue

                    fallback_role = self.get_fallback_role(current_role)
                    if fallback_role:
                        fallback_model = self.get_model_for_role(fallback_role)
                        logger.warning(
                            "llm_chain_failover_triggered",
                            from_role=current_role,
                            from_model=model_name,
                            to_role=fallback_role,
                            to_model=fallback_model,
                            reason=type(e).__name__,
                        )
                        current_role = fallback_role
                        break
                    else:
                        logger.error(
                            "llm_chain_all_attempts_failed",
                            role=current_role,
                            model=model_name,
                            error=type(e).__name__,
                        )
                        raise BusinessException(
                            ErrorCode.ALL_SERVERS_DOWN, detail=self.fallback_message
                        ) from e
                except ValueError:
                    raise

        raise BusinessException(ErrorCode.ALL_SERVERS_DOWN, detail=self.fallback_message)

    async def stream_with_failover(
        self,
        role: str,
        messages: list[BaseMessage],
        max_retries: int = 1,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        request_type: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[AIMessageChunk]:
        """
        Stream LLM response with automatic failover on connection errors (AC 1.5.2).

        Note: Failover only occurs at stream start, not mid-stream.

        Args:
            role: Initial role name for model selection.
            messages: List of messages to send.
            max_retries: Maximum retries per role before failover (default: 1).
            session_id: Session ID for LangFuse tracing (AC 1.5.4).
            user_id: User ID for LangFuse tracing (AC 1.5.4).
            request_type: Request type for metadata (e.g., "chat", "planning").
            trace_metadata: Additional metadata for LangFuse tracing.

        Yields:
            AIMessageChunk for each streamed chunk.

        Raises:
            BusinessException: With ErrorCode.ALL_SERVERS_DOWN if all servers fail.
            ValueError: If initial role doesn't exist.
        """
        langfuse_config = self._prepare_tracing_config(
            session_id=session_id,
            user_id=user_id,
            request_type=request_type,
            trace_metadata=trace_metadata,
        )

        current_role = role
        visited: set[str] = set()

        while current_role and current_role not in visited:
            visited.add(current_role)
            model_name = self.get_model_for_role(current_role)

            for attempt in range(max_retries + 1):
                try:
                    llm = self.get_llm(current_role)
                    async for chunk in llm.astream(messages, config=langfuse_config):
                        yield chunk  # type: ignore[misc]
                    return  # 스트림 완료
                except FAILOVER_EXCEPTIONS as e:
                    if attempt < max_retries:
                        logger.warning(
                            "llm_stream_retry",
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            role=current_role,
                            error=type(e).__name__,
                        )
                        continue

                    # 재시도 소진, fallback으로 전환
                    fallback_role = self.get_fallback_role(current_role)
                    if fallback_role:
                        fallback_model = self.get_model_for_role(fallback_role)
                        logger.warning(
                            "llm_stream_failover_triggered",
                            from_role=current_role,
                            from_model=model_name,
                            to_role=fallback_role,
                            to_model=fallback_model,
                            reason=type(e).__name__,
                        )
                        current_role = fallback_role
                        break
                    else:
                        # Graceful Degradation
                        logger.error(
                            "llm_stream_all_attempts_failed",
                            role=current_role,
                            model=model_name,
                            error=type(e).__name__,
                        )
                        raise BusinessException(
                            ErrorCode.ALL_SERVERS_DOWN, detail=self.fallback_message
                        ) from e
                except ValueError:
                    raise  # 존재하지 않는 역할은 그대로 전파

        # fallback 체인 끝까지 도달
        raise BusinessException(ErrorCode.ALL_SERVERS_DOWN, detail=self.fallback_message)


# Global factory instance (Singleton via get_model_config)
llm_factory = LLMFactory()
