"""LLM Provider 의존성 주입 모듈.

FastAPI Depends()에서 사용할 Provider 팩토리/싱글턴 관리.
"""

from functools import lru_cache

from src.providers.base import BaseLLMProvider
from src.providers.gateway import create_gateway_provider


@lru_cache
def get_llm_provider() -> BaseLLMProvider:
    """LLM Provider 싱글턴 인스턴스 반환.

    Usage:
        provider: BaseLLMProvider = Depends(get_llm_provider)

    Returns:
        BaseLLMProvider 구현 인스턴스.
    """
    return create_gateway_provider()
