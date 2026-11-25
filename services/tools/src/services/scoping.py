"""도구 필터링(Scoping) 서비스.

X-TOL-Scope 헤더 기반으로 도구 목록 필터링.
기능 API의 Scope 검증은 ScopeMiddleware에서 수행한다.
"""

import logging

from src.config.loader import get_allowed_scopes
from src.config.tools import ToolConfig, load_tools_config
from src.exceptions.exceptions import InvalidScopeError

logger = logging.getLogger(__name__)


def get_tools_for_scope(scope: str | None) -> list[ToolConfig]:
    """Scope에 맞는 도구 목록 반환.

    Args:
        scope: X-TOL-Scope 헤더 값. None이면 에러.

    Returns:
        필터링된 도구 목록.

    Raises:
        InvalidScopeError: Scope 미전달 또는 유효하지 않은 값.
    """
    allowed_scopes = get_allowed_scopes()

    if scope is None:
        raise InvalidScopeError(
            scope="(미전달)",
            allowed_scopes=allowed_scopes,
        )

    if scope not in allowed_scopes:
        raise InvalidScopeError(
            scope=scope,
            allowed_scopes=allowed_scopes,
        )

    tools_config = load_tools_config()
    filtered = list(tools_config.get_tools_by_scope(scope))

    logger.info(
        "도구 필터링: scope=%s, 결과=%d건",
        scope, len(filtered),
    )

    return filtered
