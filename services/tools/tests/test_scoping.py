"""도구 필터링(Scoping) 테스트.

설정 로더, 필터링 로직, 에러 처리 테스트.
"""

import pytest

from src.config.loader import get_allowed_scopes
from src.config.tools import ToolConfig, ToolsConfig, load_tools_config
from src.exceptions.exceptions import InvalidScopeError
from src.services.scoping import get_tools_for_scope


@pytest.fixture(autouse=True)
def clear_tools_cache():
    """각 테스트마다 도구 설정 캐시 클리어."""
    load_tools_config.cache_clear()
    yield
    load_tools_config.cache_clear()


# ── 설정 로더 테스트 ──


class TestToolsConfigLoader:
    """config/tools.yaml 로더 테스트."""

    def test_load_tools_config_returns_tools_config(self):
        """ToolsConfig 인스턴스 반환."""
        config = load_tools_config()
        assert isinstance(config, ToolsConfig)

    def test_load_tools_config_has_tools(self):
        """최소 1개 이상의 도구 정의 존재."""
        config = load_tools_config()
        assert len(config.tools) >= 1

    def test_tool_config_fields(self):
        """ToolConfig 필드 정합성."""
        config = load_tools_config()
        tool = config.tools[0]
        assert isinstance(tool, ToolConfig)
        assert tool.name == "summary"
        assert isinstance(tool.description, str)
        assert len(tool.description) > 0
        assert isinstance(tool.scopes, tuple)
        assert len(tool.scopes) > 0
        assert isinstance(tool.parameters, dict)

    def test_tool_config_immutable(self):
        """frozen=True 불변성 검증."""
        config = load_tools_config()
        with pytest.raises(AttributeError):
            config.tools = ()  # type: ignore[misc]

    def test_tool_config_cached(self):
        """@lru_cache 동일 인스턴스 반환."""
        config1 = load_tools_config()
        config2 = load_tools_config()
        assert config1 is config2

    def test_get_tools_by_scope_filters(self):
        """ToolsConfig.get_tools_by_scope 필터링."""
        config = load_tools_config()
        agent_tools = config.get_tools_by_scope("agent")
        assert all("agent" in t.scopes for t in agent_tools)

    def test_get_tools_by_scope_empty_for_unknown(self):
        """존재하지 않는 Scope → 빈 결과."""
        config = load_tools_config()
        result = config.get_tools_by_scope("nonexistent")
        assert len(result) == 0


# ── Scoping 헬퍼 함수 테스트 ──


class TestScopingHelpers:
    """scoping.py 내부 헬퍼 함수 테스트."""

    def test_get_allowed_scopes(self):
        """config.yaml에서 allowed_scopes 조회."""
        scopes = get_allowed_scopes()
        assert isinstance(scopes, list)
        assert set(scopes) == {"agent", "backend", "frontend"}


# ── Scoping Service 테스트 ──


class TestGetToolsForScope:
    """get_tools_for_scope() 함수 테스트."""

    def test_valid_scope_returns_tools(self):
        """유효한 Scope → 도구 목록 반환."""
        tools = get_tools_for_scope("agent")
        assert isinstance(tools, list)
        assert len(tools) > 0
        assert all(isinstance(t, ToolConfig) for t in tools)

    def test_backend_scope_returns_tools(self):
        """backend Scope → 도구 목록 반환."""
        tools = get_tools_for_scope("backend")
        assert len(tools) > 0

    def test_frontend_scope_returns_list(self):
        """frontend Scope → 빈 리스트 (tools.yaml에 frontend 도구 없음)."""
        tools = get_tools_for_scope("frontend")
        assert isinstance(tools, list)
        assert len(tools) == 0

    def test_none_scope_raises_error(self):
        """Scope None → InvalidScopeError 발생."""
        with pytest.raises(InvalidScopeError) as exc_info:
            get_tools_for_scope(None)
        assert exc_info.value.scope == "(미전달)"
        assert isinstance(exc_info.value.allowed_scopes, list)

    def test_invalid_scope_raises_error(self):
        """유효하지 않은 Scope → InvalidScopeError."""
        with pytest.raises(InvalidScopeError) as exc_info:
            get_tools_for_scope("invalid_scope")
        assert exc_info.value.scope == "invalid_scope"
        assert isinstance(exc_info.value.allowed_scopes, list)

    def test_filtered_tools_match_scope(self):
        """반환된 도구들의 scopes에 요청 Scope 포함."""
        tools = get_tools_for_scope("agent")
        for tool in tools:
            assert "agent" in tool.scopes


# ── InvalidScopeError 예외 테스트 ──


class TestInvalidScopeError:
    """InvalidScopeError 예외 테스트."""

    def test_exception_attributes(self):
        """예외 속성 정합성."""
        exc = InvalidScopeError("bad", ["agent", "backend"])
        assert exc.scope == "bad"
        assert exc.allowed_scopes == ["agent", "backend"]
        assert "bad" in str(exc)

    def test_exception_default_allowed_scopes(self):
        """allowed_scopes 미전달 시 빈 리스트."""
        exc = InvalidScopeError("bad")
        assert exc.allowed_scopes == []


# ── 전역 핸들러 통합 테스트 ──


class TestInvalidScopeHandler:
    """InvalidScopeError 전역 핸들러 테스트."""

    @pytest.mark.asyncio
    async def test_handler_returns_400(self):
        """핸들러 → HTTP 400 + TOL 표준 응답."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()

        from src.exceptions.handlers import register_exception_handlers

        register_exception_handlers(app)

        @app.get("/test-scope-error")
        async def trigger_error():
            raise InvalidScopeError("invalid", ["agent", "backend"])

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.get("/test-scope-error")
            assert resp.status_code == 400
            body = resp.json()
            assert body["code"] == "TOL010130"
            assert body["data"] is None
