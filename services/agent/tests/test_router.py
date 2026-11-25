"""Tests for Story 2.8 + Story 3.2.2: Intent Router 노드."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.workflows.main_agent import create_initial_state
from app.workflows.main_agent.nodes.router import (
    VALID_ROUTES,
    _get_default_route,
    _parse_route,
    router,
)
from app.workflows.main_agent.prompts.router import get_available_routes

ALL_ROUTES = ["direct", "rag", "tool", "both"]


class TestParseRoute:
    """Tests for _parse_route helper."""

    def test_parse_rag(self) -> None:
        assert _parse_route("rag", ALL_ROUTES) == "rag"

    def test_parse_tool(self) -> None:
        assert _parse_route("tool", ALL_ROUTES) == "tool"

    def test_parse_both(self) -> None:
        assert _parse_route("both", ALL_ROUTES) == "both"

    def test_parse_direct(self) -> None:
        assert _parse_route("direct", ALL_ROUTES) == "direct"

    def test_parse_with_whitespace(self) -> None:
        assert _parse_route("  rag  ", ALL_ROUTES) == "rag"

    def test_parse_uppercase(self) -> None:
        assert _parse_route("RAG", ALL_ROUTES) == "rag"

    def test_parse_mixed_case(self) -> None:
        assert _parse_route("Tool", ALL_ROUTES) == "tool"

    def test_parse_embedded_route(self) -> None:
        """route 값이 문장 안에 포함된 경우."""
        assert _parse_route("I think this is a rag question", ALL_ROUTES) == "rag"

    def test_parse_invalid_defaults_to_rag(self) -> None:
        assert _parse_route("unknown", ALL_ROUTES) == "rag"

    def test_parse_empty_defaults_to_rag(self) -> None:
        assert _parse_route("", ALL_ROUTES) == "rag"

    def test_parse_unavailable_route_falls_back(self) -> None:
        """가용하지 않은 경로가 반환되면 기본값으로 폴백."""
        assert _parse_route("tool", ["direct", "rag"]) == "rag"

    def test_parse_unavailable_both_falls_back(self) -> None:
        assert _parse_route("both", ["direct", "rag"]) == "rag"


class TestGetDefaultRoute:
    """Tests for _get_default_route."""

    def test_default_with_rag_available(self) -> None:
        assert _get_default_route(["direct", "rag", "tool", "both"]) == "rag"

    def test_default_with_only_tool(self) -> None:
        assert _get_default_route(["direct", "tool"]) == "tool"

    def test_default_with_only_direct(self) -> None:
        assert _get_default_route(["direct"]) == "direct"


class TestRouterNode:
    """Tests for AC 2.8.1: Intent Router 노드."""

    @pytest.fixture(autouse=True)
    def _reset_skip_flags(self) -> None:
        """env 파일 영향을 받지 않도록 SKIP 플래그를 기본값으로 초기화."""
        with patch("app.workflows.main_agent.nodes.router.get_available_routes", wraps=get_available_routes):
            from app.core.config import settings
            self._orig_skip_tool = settings.SKIP_TOOL
            self._orig_skip_rag = settings.SKIP_RAG
            self._orig_skip_direct = settings.SKIP_DIRECT
            settings.SKIP_TOOL = False
            settings.SKIP_RAG = False
            settings.SKIP_DIRECT = True
            yield
            settings.SKIP_TOOL = self._orig_skip_tool
            settings.SKIP_RAG = self._orig_skip_rag
            settings.SKIP_DIRECT = self._orig_skip_direct

    @pytest.mark.asyncio
    async def test_router_returns_route_and_thoughts(self) -> None:
        """Test router returns route and thoughts fields."""
        state = create_initial_state(query="테스트", session_id="test-123")
        state["standalone_query"] = "테스트 질문"

        mock_response = AIMessage(content="rag")
        with patch(
            "app.workflows.main_agent.nodes.router.llm_factory"
        ) as mock_factory:
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            result = await router(state)

        assert "route" in result
        assert "thoughts" in result
        assert result["route"] in VALID_ROUTES

    @pytest.mark.asyncio
    async def test_router_rag_route(self) -> None:
        """Test router returns rag route."""
        state = create_initial_state(query="사내문서 검색해줘", session_id="test-123")
        state["standalone_query"] = "사내문서 검색해줘"

        mock_response = AIMessage(content="rag")
        with patch(
            "app.workflows.main_agent.nodes.router.llm_factory"
        ) as mock_factory:
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            result = await router(state)

        assert result["route"] == "rag"
        assert "RAG 경로" in result["thoughts"][0]

    @pytest.mark.asyncio
    async def test_router_tool_route(self) -> None:
        """Test router returns tool route."""
        state = create_initial_state(query="날씨 알려줘", session_id="test-123")
        state["standalone_query"] = "날씨 알려줘"

        mock_response = AIMessage(content="tool")
        with patch(
            "app.workflows.main_agent.nodes.router.llm_factory"
        ) as mock_factory:
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            result = await router(state)

        assert result["route"] == "tool"
        assert "Tool 경로" in result["thoughts"][0]

    @pytest.mark.asyncio
    async def test_router_both_route(self) -> None:
        """Test router returns both route."""
        state = create_initial_state(query="문서 찾아서 계산해줘", session_id="test-123")
        state["standalone_query"] = "문서 찾아서 계산해줘"

        mock_response = AIMessage(content="both")
        with patch(
            "app.workflows.main_agent.nodes.router.llm_factory"
        ) as mock_factory:
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            result = await router(state)

        assert result["route"] == "both"
        assert "병렬 경로" in result["thoughts"][0]

    @pytest.mark.asyncio
    async def test_router_fallback_on_invalid_response(self) -> None:
        """Test router defaults to rag on invalid LLM response."""
        state = create_initial_state(query="테스트", session_id="test-123")
        state["standalone_query"] = "테스트"

        mock_response = AIMessage(content="invalid_response")
        with patch(
            "app.workflows.main_agent.nodes.router.llm_factory"
        ) as mock_factory:
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            result = await router(state)

        assert result["route"] == "rag"

    @pytest.mark.asyncio
    async def test_router_fallback_on_exception(self) -> None:
        """Test router defaults to rag on exception."""
        from app.core.enums import ErrorCode
        from app.core.exceptions import BusinessException

        state = create_initial_state(query="테스트", session_id="test-123")
        state["standalone_query"] = "테스트"

        with patch(
            "app.workflows.main_agent.nodes.router.llm_factory"
        ) as mock_factory:
            mock_factory.invoke_chain_with_failover = AsyncMock(
                side_effect=BusinessException(ErrorCode.LLM_CONNECTION)
            )
            result = await router(state)

        assert result["route"] == "rag"
        assert len(result["thoughts"]) == 1

    @pytest.mark.asyncio
    async def test_router_uses_standalone_query(self) -> None:
        """Test router uses standalone_query over original query."""
        state = create_initial_state(query="원본 질문", session_id="test-123")
        state["standalone_query"] = "재구성된 질문"

        mock_response = AIMessage(content="rag")
        with patch(
            "app.workflows.main_agent.nodes.router.llm_factory"
        ) as mock_factory:
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            await router(state)

        call_kwargs = mock_factory.invoke_chain_with_failover.call_args
        # trace_metadata에 재구성된 질문이 포함되어야 함
        assert call_kwargs.kwargs["trace_metadata"]["query"] == "재구성된 질문"

    @pytest.mark.asyncio
    async def test_router_thoughts_self_only(self) -> None:
        """Test router returns only its own thought (reducer pattern)."""
        state = create_initial_state(query="테스트", session_id="test-123")
        state["standalone_query"] = "테스트"
        state["thoughts"] = ["이전 thought"]

        mock_response = AIMessage(content="rag")
        with patch(
            "app.workflows.main_agent.nodes.router.llm_factory"
        ) as mock_factory:
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            result = await router(state)

        # reducer 패턴: 자기 것만 반환
        assert len(result["thoughts"]) == 1

    @pytest.mark.asyncio
    async def test_router_uses_fast_role(self) -> None:
        """Test router uses 'fast' role model (AC 2.8.3)."""
        state = create_initial_state(query="테스트", session_id="test-123")
        state["standalone_query"] = "테스트"

        mock_response = AIMessage(content="rag")
        with patch(
            "app.workflows.main_agent.nodes.router.llm_factory"
        ) as mock_factory:
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            await router(state)

        call_kwargs = mock_factory.invoke_chain_with_failover.call_args
        assert call_kwargs.kwargs["role"] == "fast"

    @pytest.mark.asyncio
    async def test_router_direct_route(self) -> None:
        """Test router returns direct route (AC 3.2.2.7, SKIP_DIRECT=false)."""
        state = create_initial_state(query="안녕하세요", session_id="test-123")
        state["standalone_query"] = "안녕하세요"

        mock_response = AIMessage(content="direct")
        with (
            patch("app.workflows.main_agent.nodes.router.get_available_routes", return_value=["direct", "rag", "tool", "both"]),
            patch("app.workflows.main_agent.nodes.router.llm_factory") as mock_factory,
        ):
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            result = await router(state)

        assert result["route"] == "direct"
        assert "Direct 경로" in result["thoughts"][0]


class TestRouterSkipFlags:
    """Tests for AC 3.2.2.5~6: SKIP 플래그 기반 경로 제한."""

    @pytest.mark.asyncio
    async def test_skip_tool_excludes_tool_routes(self) -> None:
        """SKIP_TOOL=true일 때 tool, both 경로 선택 불가 (AC 3.2.2.5)."""
        state = create_initial_state(query="날씨 알려줘", session_id="test-123")
        state["standalone_query"] = "날씨 알려줘"

        mock_response = AIMessage(content="tool")
        with (
            patch("app.workflows.main_agent.nodes.router.get_available_routes", return_value=["direct", "rag"]),
            patch("app.workflows.main_agent.nodes.router.llm_factory") as mock_factory,
        ):
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            result = await router(state)

        assert result["route"] in ("rag", "direct")
        assert result["route"] not in ("tool", "both")

    @pytest.mark.asyncio
    async def test_skip_rag_excludes_rag_routes(self) -> None:
        """SKIP_RAG=true일 때 rag, both 경로 선택 불가."""
        state = create_initial_state(query="사내문서 검색해줘", session_id="test-123")
        state["standalone_query"] = "사내문서 검색해줘"

        mock_response = AIMessage(content="rag")
        with (
            patch("app.workflows.main_agent.nodes.router.get_available_routes", return_value=["direct", "tool"]),
            patch("app.workflows.main_agent.nodes.router.llm_factory") as mock_factory,
        ):
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            result = await router(state)

        assert result["route"] in ("tool", "direct")
        assert result["route"] not in ("rag", "both")

    @pytest.mark.asyncio
    async def test_skip_both_returns_direct(self) -> None:
        """SKIP_RAG=true, SKIP_TOOL=true, SKIP_DIRECT=false일 때 direct."""
        state = create_initial_state(query="아무 질문이나", session_id="test-123")
        state["standalone_query"] = "아무 질문이나"

        with patch(
            "app.workflows.main_agent.nodes.router.get_available_routes",
            return_value=["direct"],
        ):
            result = await router(state)

        assert result["route"] == "direct"

    @pytest.mark.asyncio
    async def test_skip_direct_excludes_direct_route(self) -> None:
        """SKIP_DIRECT=true일 때 direct 경로 선택 불가 (AC 3.3.2)."""
        state = create_initial_state(query="안녕하세요", session_id="test-123")
        state["standalone_query"] = "안녕하세요"

        mock_response = AIMessage(content="direct")
        with (
            patch("app.workflows.main_agent.nodes.router.get_available_routes", return_value=["rag", "tool", "both"]),
            patch("app.workflows.main_agent.nodes.router.llm_factory") as mock_factory,
        ):
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)
            result = await router(state)

        assert result["route"] != "direct"
        assert result["route"] in ("rag", "tool", "both")

    @pytest.mark.asyncio
    async def test_skip_all_falls_back_to_rag(self) -> None:
        """SKIP_RAG=true, SKIP_TOOL=true, SKIP_DIRECT=true일 때 rag fallback."""
        state = create_initial_state(query="아무 질문이나", session_id="test-123")
        state["standalone_query"] = "아무 질문이나"

        with patch(
            "app.workflows.main_agent.nodes.router.get_available_routes",
            return_value=[],
        ):
            result = await router(state)

        assert result["route"] == "rag"


class TestGetAvailableRoutes:
    """Tests for get_available_routes SKIP 매트릭스."""

    def test_all_enabled(self) -> None:
        with (
            patch("app.workflows.main_agent.prompts.router.settings") as mock_settings,
        ):
            mock_settings.SKIP_RAG = False
            mock_settings.SKIP_TOOL = False
            mock_settings.SKIP_DIRECT = False
            routes = get_available_routes()
        assert "rag" in routes
        assert "tool" in routes
        assert "both" in routes
        assert "direct" in routes

    def test_skip_tool(self) -> None:
        with patch("app.workflows.main_agent.prompts.router.settings") as mock_settings:
            mock_settings.SKIP_RAG = False
            mock_settings.SKIP_TOOL = True
            mock_settings.SKIP_DIRECT = False
            routes = get_available_routes()
        assert "rag" in routes
        assert "direct" in routes
        assert "tool" not in routes
        assert "both" not in routes

    def test_skip_rag(self) -> None:
        with patch("app.workflows.main_agent.prompts.router.settings") as mock_settings:
            mock_settings.SKIP_RAG = True
            mock_settings.SKIP_TOOL = False
            mock_settings.SKIP_DIRECT = False
            routes = get_available_routes()
        assert "tool" in routes
        assert "direct" in routes
        assert "rag" not in routes
        assert "both" not in routes

    def test_skip_both_rag_tool(self) -> None:
        with patch("app.workflows.main_agent.prompts.router.settings") as mock_settings:
            mock_settings.SKIP_RAG = True
            mock_settings.SKIP_TOOL = True
            mock_settings.SKIP_DIRECT = False
            routes = get_available_routes()
        assert routes == ["direct"]

    def test_skip_direct(self) -> None:
        """SKIP_DIRECT=true일 때 direct 제외 (AC 3.3.2)."""
        with patch("app.workflows.main_agent.prompts.router.settings") as mock_settings:
            mock_settings.SKIP_RAG = False
            mock_settings.SKIP_TOOL = False
            mock_settings.SKIP_DIRECT = True
            routes = get_available_routes()
        assert "rag" in routes
        assert "tool" in routes
        assert "both" in routes
        assert "direct" not in routes

    def test_skip_direct_and_tool(self) -> None:
        """SKIP_DIRECT=true, SKIP_TOOL=true일 때 rag만."""
        with patch("app.workflows.main_agent.prompts.router.settings") as mock_settings:
            mock_settings.SKIP_RAG = False
            mock_settings.SKIP_TOOL = True
            mock_settings.SKIP_DIRECT = True
            routes = get_available_routes()
        assert routes == ["rag"]

    def test_skip_all(self) -> None:
        """모든 SKIP=true일 때 빈 리스트."""
        with patch("app.workflows.main_agent.prompts.router.settings") as mock_settings:
            mock_settings.SKIP_RAG = True
            mock_settings.SKIP_TOOL = True
            mock_settings.SKIP_DIRECT = True
            routes = get_available_routes()
        assert routes == []


class TestRouterPromptContent:
    """Tests for AC 3.2.2.4: Router 프롬프트 2단계 판단."""

    def test_prompt_has_keyword_matching_section(self) -> None:
        """프롬프트에 키워드 매칭 기준이 포함되어 있다."""
        from app.workflows.main_agent.prompts.router import build_router_prompt
        prompt = build_router_prompt(["direct", "rag", "tool", "both"])
        system_msg = prompt.format_messages(query="")[0].content
        assert "키워드 매칭" in system_msg

    def test_prompt_has_intent_analysis_section(self) -> None:
        """프롬프트에 의도 분석 기준이 포함되어 있다."""
        from app.workflows.main_agent.prompts.router import build_router_prompt
        prompt = build_router_prompt(["direct", "rag", "tool", "both"])
        system_msg = prompt.format_messages(query="")[0].content
        assert "의도 분석" in system_msg

    def test_prompt_has_few_shot_examples(self) -> None:
        """프롬프트에 few-shot 예시가 포함되어 있다."""
        from app.workflows.main_agent.prompts.router import build_router_prompt
        prompt = build_router_prompt(["direct", "rag", "tool", "both"])
        system_msg = prompt.format_messages(query="")[0].content
        assert "안녕하세요" in system_msg
        assert "→ direct" in system_msg
        assert "→ rag" in system_msg

    def test_prompt_excludes_unavailable_routes(self) -> None:
        """비활성 경로는 프롬프트에 표시되지 않는다."""
        from app.workflows.main_agent.prompts.router import build_router_prompt
        prompt = build_router_prompt(["direct", "rag"])
        system_msg = prompt.format_messages(query="")[0].content
        assert "direct" in system_msg
        assert "rag" in system_msg
        # tool 경로 설명이 없어야 함
        assert "tool: 외부 도구" not in system_msg


class TestRouteByIntent:
    """Tests for AC 3.2.2.8: Graph direct 엣지."""

    def test_direct_route(self) -> None:
        from app.workflows.main_agent.graph import route_by_intent
        state = {"route": "direct"}
        assert route_by_intent(state) == "direct"

    def test_both_route_fan_out(self) -> None:
        from app.workflows.main_agent.graph import route_by_intent
        state = {"route": "both"}
        assert route_by_intent(state) == ["rag", "tool"]

    def test_rag_route(self) -> None:
        from app.workflows.main_agent.graph import route_by_intent
        state = {"route": "rag"}
        assert route_by_intent(state) == "rag"
