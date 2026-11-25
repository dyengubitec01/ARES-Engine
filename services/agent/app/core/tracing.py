"""
LangFuse Tracing Setup.

LangFuse 추적 설정 (Story 1.5)
- AC 1.5.1: LangFuse 초기화
- AC 1.5.2: LLM 호출 자동 추적
- AC 1.5.5: 비활성화 모드

LangFuse SDK v3 사용 (langfuse.langchain.CallbackHandler)
- LangChain 1.x 지원
- Server V3 (>= 3.63.0) 필요

SDK v3 API 변경 사항:
- 환경 변수에서 자동으로 키 읽음 (LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_HOST)
- CallbackHandler 초기화 시 public_key만 선택적 전달
- session_id, user_id 등은 chain 호출 시 config metadata로 전달
"""

import os
from typing import Any

import structlog
from langchain_core.callbacks import BaseCallbackHandler

from app.core.config import settings

logger = structlog.get_logger()


class TracingManager:
    """LangFuse tracing manager with callback handler factory."""

    def __init__(self) -> None:
        self._enabled: bool = False
        self._initialized: bool = False

    def initialize(self) -> None:
        """
        Initialize LangFuse if configured (AC 1.5.1).

        서버 시작 시 한 번만 호출되어야 함 (Eager Initialization).
        환경 변수가 없으면 추적이 비활성화된다 (에러 없이).
        SDK v3는 환경 변수에서 자동으로 키를 읽음.
        """
        if self._initialized:
            return

        self._initialized = True

        if not settings.langfuse_enabled:
            logger.warning("LangFuse not configured, tracing disabled")
            return

        try:
            # langfuse 패키지 존재 여부 확인
            import langfuse  # noqa: F401

            # SDK v3: OS 환경변수 설정 (pydantic-settings에서 읽은 값)
            # LangFuse SDK는 os.environ에서 직접 읽음
            if settings.LANGFUSE_PUBLIC_KEY:
                os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
            if settings.LANGFUSE_SECRET_KEY:
                os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
            if settings.LANGFUSE_HOST:
                os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST

            self._enabled = True
            logger.info("langfuse_tracing_enabled", host=settings.LANGFUSE_HOST)
        except ImportError:
            logger.warning(
                "LangFuse package not installed, tracing disabled. "
                "Install with: pip install 'agent-server[tracing]'"
            )

    @property
    def enabled(self) -> bool:
        """Check if tracing is enabled."""
        if not self._initialized:
            self.initialize()
        return self._enabled

    def get_callback_handler(self) -> BaseCallbackHandler | None:
        """
        Get LangFuse callback handler for LangChain integration (AC 1.5.2).

        SDK v3에서는 CallbackHandler가 환경 변수에서 자동으로 키를 읽습니다.
        session_id, user_id 등 메타데이터는 get_langfuse_config()를 사용하여
        chain 호출 시 config로 전달해야 합니다.

        Returns:
            CallbackHandler instance if LangFuse is enabled, None otherwise.

        Example:
            # 단순 handler만 필요한 경우
            handler = tracing.get_callback_handler()

            # 메타데이터가 필요한 경우 (권장)
            config = tracing.get_langfuse_config(
                session_id="session-123",
                user_id="user-456",
            )
            response = await llm.ainvoke(messages, config=config)
        """
        if not self.enabled:
            return None

        try:
            # SDK v3: langfuse.langchain에서 import
            from langfuse.langchain import CallbackHandler

            # SDK v3: 환경변수에서 자동으로 키를 읽음
            # update_trace=True: root span의 name이 trace name으로 설정됨
            handler = CallbackHandler(update_trace=True)
            return handler
        except ImportError as e:
            logger.warning("langfuse_integration_unavailable", error=str(e))
            return None
        except Exception as e:
            logger.warning("langfuse_callback_creation_failed", error=str(e))
            return None

    def get_callbacks(self) -> list[BaseCallbackHandler]:
        """
        Get list of callback handlers for LangChain.

        Convenience method that returns a list suitable for LangChain's
        callbacks parameter. 메타데이터가 필요한 경우 get_langfuse_config() 사용을 권장.

        Returns:
            List of callback handlers (empty if tracing disabled).

        Example:
            # callbacks 리스트로 직접 전달 (메타데이터 없이)
            callbacks = tracing.get_callbacks()
            response = await llm.ainvoke(messages, config={"callbacks": callbacks})

            # 메타데이터가 필요한 경우 (권장)
            config = tracing.get_langfuse_config(session_id="session-123")
            response = await llm.ainvoke(messages, config=config)
        """
        handler = self.get_callback_handler()
        return [handler] if handler else []

    def get_langfuse_config(
        self,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        run_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Get LangChain config with LangFuse metadata (SDK v3 방식).

        SDK v3에서는 session_id, user_id 등을 config metadata로 전달해야 함.

        Args:
            session_id: Session ID for grouping conversations.
            user_id: Optional user identifier.
            tags: Optional list of tags for filtering.
            metadata: Additional metadata.

        Returns:
            Config dict for chain.invoke(input, config=config).

        Example:
            config = tracing.get_langfuse_config(
                session_id="session-123",
                user_id="user-456",
            )
            response = await llm.ainvoke(messages, config=config)
        """
        handler = self.get_callback_handler()

        config: dict[str, Any] = {}

        if handler:
            config["callbacks"] = [handler]

        # SDK v3: langfuse_ 접두사로 메타데이터 전달
        config_metadata: dict[str, Any] = {}
        if session_id:
            config_metadata["langfuse_session_id"] = session_id
        if user_id:
            config_metadata["langfuse_user_id"] = user_id
        if tags:
            config_metadata["langfuse_tags"] = tags
        if metadata:
            config_metadata.update(metadata)

        if config_metadata:
            config["metadata"] = config_metadata

        if run_name:
            config["run_name"] = run_name

        return config


# Global tracing manager instance (Singleton)
tracing = TracingManager()
