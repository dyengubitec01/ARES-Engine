"""Tests for Tool Client - Story 2.4, Story 2.8 (MCP → Tool rename)."""

from unittest.mock import patch

import pytest

from app.clients.tool_client import (
    MockToolClient,
    ToolClient,
    ToolClientProtocol,
    ToolDefinition,
    ToolResult,
    get_tool_client,
)


class TestToolDefinition:
    """Tests for ToolDefinition model (AC 2.4.1)."""

    def test_tool_definition_creation(self) -> None:
        """Test ToolDefinition can be created with required fields."""
        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"arg1": {"type": "string"}},
        )

        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.parameters == {"arg1": {"type": "string"}}

    def test_tool_definition_json_schema_parameters(self) -> None:
        """Test ToolDefinition supports JSON Schema style parameters."""
        tool = ToolDefinition(
            name="complex_tool",
            description="Tool with complex params",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "Location"},
                },
                "required": ["location"],
            },
        )

        assert tool.parameters["type"] == "object"
        assert "location" in tool.parameters["properties"]


class TestToolResult:
    """Tests for ToolResult model (AC 2.4.1)."""

    def test_tool_result_success(self) -> None:
        """Test ToolResult for successful execution."""
        result = ToolResult(
            success=True,
            result={"data": "value"},
            error=None,
        )

        assert result.success is True
        assert result.result == {"data": "value"}
        assert result.error is None

    def test_tool_result_failure(self) -> None:
        """Test ToolResult for failed execution."""
        result = ToolResult(
            success=False,
            result=None,
            error="Tool execution failed",
        )

        assert result.success is False
        assert result.result is None
        assert result.error == "Tool execution failed"

    def test_tool_result_default_error(self) -> None:
        """Test ToolResult error field defaults to None."""
        result = ToolResult(success=True, result={})

        assert result.error is None


class TestToolClientProtocol:
    """Tests for ToolClientProtocol interface (AC 2.4.1)."""

    def test_mock_client_implements_protocol(self) -> None:
        """Test MockToolClient implements ToolClientProtocol."""
        client = MockToolClient()

        assert isinstance(client, ToolClientProtocol)

    def test_protocol_has_list_tools(self) -> None:
        """Test protocol defines list_tools method."""
        assert hasattr(ToolClientProtocol, "list_tools")

    def test_protocol_has_call_tool(self) -> None:
        """Test protocol defines call_tool method."""
        assert hasattr(ToolClientProtocol, "call_tool")


class TestMockToolClient:
    """Tests for MockToolClient implementation (AC 2.4.2, AC 2.4.3)."""

    @pytest.fixture
    def mock_client(self) -> MockToolClient:
        """Create MockToolClient instance."""
        return MockToolClient()

    @pytest.mark.asyncio
    async def test_list_tools_returns_tools(self, mock_client: MockToolClient) -> None:
        """Test list_tools returns sample tool list (AC 2.4.2)."""
        tools = await mock_client.list_tools()

        assert len(tools) >= 2
        assert all(isinstance(t, ToolDefinition) for t in tools)

    @pytest.mark.asyncio
    async def test_list_tools_contains_get_weather(
        self, mock_client: MockToolClient
    ) -> None:
        """Test list_tools includes get_weather tool (AC 2.4.2)."""
        tools = await mock_client.list_tools()
        tool_names = [t.name for t in tools]

        assert "get_weather" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_contains_calculate(
        self, mock_client: MockToolClient
    ) -> None:
        """Test list_tools includes calculate tool (AC 2.4.2)."""
        tools = await mock_client.list_tools()
        tool_names = [t.name for t in tools]

        assert "calculate" in tool_names

    @pytest.mark.asyncio
    async def test_call_tool_get_weather_seoul(
        self, mock_client: MockToolClient
    ) -> None:
        """Test call_tool with get_weather for Seoul (AC 2.4.3)."""
        result = await mock_client.call_tool(
            "get_weather", {"location": "서울"}
        )

        assert result.success is True
        assert result.error is None
        assert result.result["temperature"] == 5
        assert result.result["condition"] == "맑음"
        assert result.result["humidity"] == 45

    @pytest.mark.asyncio
    async def test_call_tool_get_weather_default_location(
        self, mock_client: MockToolClient
    ) -> None:
        """Test call_tool with get_weather uses default for unknown location."""
        result = await mock_client.call_tool(
            "get_weather", {"location": "뉴욕"}
        )

        assert result.success is True
        # Unknown location returns default values
        assert "temperature" in result.result

    @pytest.mark.asyncio
    async def test_call_tool_calculate(self, mock_client: MockToolClient) -> None:
        """Test call_tool with calculate returns mock result."""
        result = await mock_client.call_tool(
            "calculate", {"expression": "1+1"}
        )

        assert result.success is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self, mock_client: MockToolClient) -> None:
        """Test call_tool with unknown tool returns error."""
        result = await mock_client.call_tool(
            "unknown_tool", {}
        )

        assert result.success is False
        assert result.error is not None
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_call_tool_missing_required_argument_location(
        self, mock_client: MockToolClient
    ) -> None:
        """Test call_tool with missing required argument for get_weather."""
        result = await mock_client.call_tool("get_weather", {})

        assert result.success is False
        assert result.error is not None
        assert "Missing required argument" in result.error
        assert "location" in result.error

    @pytest.mark.asyncio
    async def test_call_tool_missing_required_argument_expression(
        self, mock_client: MockToolClient
    ) -> None:
        """Test call_tool with missing required argument for calculate."""
        result = await mock_client.call_tool("calculate", {})

        assert result.success is False
        assert result.error is not None
        assert "Missing required argument" in result.error
        assert "expression" in result.error


class TestToolClient:
    """Tests for ToolClient skeleton (AC 2.4.4)."""

    def test_tool_client_init_default_settings(self) -> None:
        """Test ToolClient uses default settings when no args provided."""
        client = ToolClient()

        assert client.base_url is not None
        assert client.timeout is not None

    def test_tool_client_init_custom_settings(self) -> None:
        """Test ToolClient accepts custom base_url and timeout."""
        client = ToolClient(
            base_url="http://custom:9000",
            timeout=60.0,
        )

        assert client.base_url == "http://custom:9000"
        assert client.timeout == 60.0

    @pytest.mark.asyncio
    async def test_list_tools_connection_error(self) -> None:
        """Test list_tools raises BusinessException on connection failure (AC 2.8.9)."""
        from app.core.exceptions import BusinessException

        client = ToolClient(base_url="http://localhost:19999", timeout=1.0)

        with pytest.raises(BusinessException):
            await client.list_tools()

    @pytest.mark.asyncio
    async def test_call_tool_connection_error(self) -> None:
        """Test call_tool raises BusinessException on connection failure (AC 2.8.9)."""
        from app.core.exceptions import BusinessException

        client = ToolClient(base_url="http://localhost:19999", timeout=1.0)

        with pytest.raises(BusinessException):
            await client.call_tool("test", {})

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test ToolClient can be used as context manager."""
        async with ToolClient() as client:
            assert client is not None

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """Test ToolClient close method."""
        client = ToolClient()
        await client.close()

        assert client._client is None

    def test_tool_client_has_lock(self) -> None:
        """Test ToolClient has thread-safe lock."""
        from asyncio import Lock

        client = ToolClient()

        assert hasattr(client, "_client_lock")
        assert isinstance(client._client_lock, Lock)

    @pytest.mark.asyncio
    async def test_get_client_creates_httpx_client(self) -> None:
        """Test _get_client creates httpx.AsyncClient."""
        import httpx

        client = ToolClient()
        http_client = await client._get_client()

        assert isinstance(http_client, httpx.AsyncClient)
        await client.close()


class TestGetToolClient:
    """Tests for get_tool_client factory function (AC 2.4.5)."""

    def test_get_mock_client_when_use_mock_true(self) -> None:
        """Test get_tool_client returns MockToolClient when USE_MOCK_TOOL=True."""
        with patch("app.clients.tool_client.get_settings") as mock_settings:
            mock_settings.return_value.USE_MOCK_TOOL = True

            client = get_tool_client()

            assert isinstance(client, MockToolClient)

    def test_get_real_client_when_use_mock_false(self) -> None:
        """Test get_tool_client returns ToolClient when USE_MOCK_TOOL=False."""
        with patch("app.clients.tool_client.get_settings") as mock_settings:
            mock_settings.return_value.USE_MOCK_TOOL = False
            mock_settings.return_value.TOOL_BASE_URL = "http://test:8002"
            mock_settings.return_value.TOOL_TIMEOUT = 30.0

            client = get_tool_client()

            assert isinstance(client, ToolClient)

    def test_factory_uses_settings_for_real_client(self) -> None:
        """Test factory passes settings to ToolClient."""
        with patch("app.clients.tool_client.get_settings") as mock_settings:
            mock_settings.return_value.USE_MOCK_TOOL = False
            mock_settings.return_value.TOOL_BASE_URL = "http://custom:9000"
            mock_settings.return_value.TOOL_TIMEOUT = 45.0

            client = get_tool_client()

            assert client.base_url == "http://custom:9000"
            assert client.timeout == 45.0


class TestToolConfigSettings:
    """Tests for Tool configuration in Settings."""

    def test_tool_settings_defaults(self) -> None:
        """Test Tool settings have correct defaults."""
        from app.core.config import Settings

        settings = Settings(_env_file=None)

        assert settings.USE_MOCK_TOOL is True
        assert settings.TOOL_BASE_URL == "http://localhost:8007"
        assert settings.TOOL_TIMEOUT == 30.0

    def test_tool_settings_can_be_overridden(self) -> None:
        """Test Tool settings can be overridden."""
        from app.core.config import Settings

        settings = Settings(
            USE_MOCK_TOOL=False,
            TOOL_BASE_URL="http://custom:9000",
            TOOL_TIMEOUT=60.0,
        )

        assert settings.USE_MOCK_TOOL is False
        assert settings.TOOL_BASE_URL == "http://custom:9000"
        assert settings.TOOL_TIMEOUT == 60.0
