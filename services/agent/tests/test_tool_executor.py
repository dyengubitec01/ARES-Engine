"""Tests for Story 2.8: Tool Executor 노드."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.runnables import RunnableConfig

from app.clients.tool_client import ToolDefinition, ToolResult
from app.workflows.main_agent import create_initial_state
from app.workflows.main_agent.nodes.tool_executor import (
    _build_arguments,
    _extract_location,
    _select_tool,
    tool_executor,
)

TEST_CONFIG: RunnableConfig = {"callbacks": []}

SAMPLE_TOOLS = [
    ToolDefinition(
        name="get_weather",
        description="현재 날씨 정보 조회",
        parameters={"location": {"type": "string"}},
    ),
    ToolDefinition(
        name="calculate",
        description="수학 계산 수행",
        parameters={"expression": {"type": "string"}},
    ),
]


class TestSelectTool:
    """Tests for _select_tool helper."""

    def test_select_by_name_match(self) -> None:
        tool = _select_tool(SAMPLE_TOOLS, "get_weather 서울")
        assert tool.name == "get_weather"

    def test_select_by_name_calculate(self) -> None:
        tool = _select_tool(SAMPLE_TOOLS, "calculate 실행해줘")
        assert tool.name == "calculate"

    def test_select_default_first_tool(self) -> None:
        tool = _select_tool(SAMPLE_TOOLS, "관련없는 질문")
        assert tool.name == "get_weather"  # 첫 번째 도구


class TestBuildArguments:
    """Tests for _build_arguments helper."""

    def test_weather_arguments(self) -> None:
        args = _build_arguments("get_weather", "서울 날씨 알려줘")
        assert args == {"location": "서울"}

    def test_calculate_arguments(self) -> None:
        args = _build_arguments("calculate", "1+1")
        assert args == {"expression": "1+1"}

    def test_unknown_tool_arguments(self) -> None:
        args = _build_arguments("unknown", "질문")
        assert args == {"query": "질문"}


class TestExtractLocation:
    """Tests for _extract_location helper."""

    def test_extract_seoul(self) -> None:
        assert _extract_location("서울 날씨") == "서울"

    def test_extract_busan(self) -> None:
        assert _extract_location("부산 날씨 알려줘") == "부산"

    def test_default_seoul(self) -> None:
        assert _extract_location("날씨 알려줘") == "서울"


class TestToolExecutorNode:
    """Tests for AC 2.8.4: Tool Executor 노드."""

    @pytest.mark.asyncio
    async def test_tool_executor_returns_context_and_thoughts(self) -> None:
        """Test tool_executor returns context and thoughts."""
        state = create_initial_state(query="서울 날씨", session_id="test-123")
        state["standalone_query"] = "서울 날씨 알려줘"

        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=SAMPLE_TOOLS)
        mock_client.call_tool = AsyncMock(
            return_value=ToolResult(
                success=True,
                result={"temperature": 5, "condition": "맑음"},
            )
        )

        with patch(
            "app.workflows.main_agent.nodes.tool_executor.get_tool_client",
            return_value=mock_client,
        ):
            result = await tool_executor(state, TEST_CONFIG)

        assert "context" in result
        assert "thoughts" in result
        assert len(result["context"]) == 1
        assert "[도구 결과" in result["context"][0]

    @pytest.mark.asyncio
    async def test_tool_executor_empty_tools(self) -> None:
        """Test tool_executor handles no tools available."""
        state = create_initial_state(query="테스트", session_id="test-123")
        state["standalone_query"] = "테스트"

        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=[])

        with patch(
            "app.workflows.main_agent.nodes.tool_executor.get_tool_client",
            return_value=mock_client,
        ):
            result = await tool_executor(state, TEST_CONFIG)

        assert result["context"] == []
        assert "사용 가능한 도구가 없습니다" in result["thoughts"][0]

    @pytest.mark.asyncio
    async def test_tool_executor_tool_failure(self) -> None:
        """Test tool_executor handles tool execution failure."""
        state = create_initial_state(query="서울 날씨", session_id="test-123")
        state["standalone_query"] = "서울 날씨"

        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=SAMPLE_TOOLS)
        mock_client.call_tool = AsyncMock(
            return_value=ToolResult(
                success=False, result=None, error="도구 오류 발생"
            )
        )

        with patch(
            "app.workflows.main_agent.nodes.tool_executor.get_tool_client",
            return_value=mock_client,
        ):
            result = await tool_executor(state, TEST_CONFIG)

        assert len(result["context"]) == 1
        assert "[도구 오류" in result["context"][0]

    @pytest.mark.asyncio
    async def test_tool_executor_exception_handling(self) -> None:
        """Test tool_executor returns error context on failure."""
        from app.core.enums import ErrorCode
        from app.core.exceptions import BusinessException

        state = create_initial_state(query="테스트", session_id="test-123")
        state["standalone_query"] = "테스트"

        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(
            side_effect=BusinessException(ErrorCode.TOOL_EXECUTION)
        )

        with patch(
            "app.workflows.main_agent.nodes.tool_executor.get_tool_client",
            return_value=mock_client,
        ):
            result = await tool_executor(state, TEST_CONFIG)

        assert len(result["context"]) == 1
        assert "[도구 오류]" in result["context"][0]
        assert "실패" in result["thoughts"][0]

    @pytest.mark.asyncio
    async def test_tool_executor_thoughts_self_only(self) -> None:
        """Test tool_executor returns only its own thought (reducer pattern)."""
        state = create_initial_state(query="서울 날씨", session_id="test-123")
        state["standalone_query"] = "서울 날씨"
        state["thoughts"] = ["이전 thought"]

        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(return_value=SAMPLE_TOOLS)
        mock_client.call_tool = AsyncMock(
            return_value=ToolResult(success=True, result={"temp": 5})
        )

        with patch(
            "app.workflows.main_agent.nodes.tool_executor.get_tool_client",
            return_value=mock_client,
        ):
            result = await tool_executor(state, TEST_CONFIG)

        # reducer 패턴: 자기 것만 반환
        assert len(result["thoughts"]) == 1
