"""
Tool Client Interface and Implementations.

Story 2.4: 도구 클라이언트 인터페이스와 구현체 제공.
Story 2.8: MCP → Tool 명칭 변경.
"""

from asyncio import Lock
from typing import Any, Protocol, runtime_checkable

import httpx
import structlog
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.enums import ErrorCode
from app.core.exceptions import BusinessException

logger = structlog.get_logger()


class ToolDefinition(BaseModel):
    """도구 정의 모델 (AC 2.4.1).

    Attributes:
        name: 도구 이름
        description: 도구 설명
        parameters: JSON Schema 형식의 파라미터 정의
    """

    name: str
    description: str
    parameters: dict


class ToolResult(BaseModel):
    """도구 실행 결과 모델 (AC 2.4.1).

    Attributes:
        success: 실행 성공 여부
        result: 실행 결과 (성공 시)
        error: 에러 메시지 (실패 시)
    """

    success: bool
    result: Any
    error: str | None = None


@runtime_checkable
class ToolClientProtocol(Protocol):
    """Tool Client 인터페이스 프로토콜 (AC 2.4.1).

    모든 Tool 클라이언트는 이 프로토콜을 구현해야 합니다.
    """

    async def list_tools(
        self,
        trace_id: str | None = None,
        observation_id: str | None = None,
    ) -> list[ToolDefinition]:
        """사용 가능한 도구 목록 조회.

        Args:
            trace_id: LangFuse trace_id (X-LF-Trace-ID 헤더)
            observation_id: LangFuse observation_id (X-LF-Parent-Id 헤더)

        Returns:
            도구 정의 목록
        """
        ...

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        trace_id: str | None = None,
        observation_id: str | None = None,
    ) -> ToolResult:
        """도구 실행.

        Args:
            tool_name: 실행할 도구 이름
            arguments: 도구에 전달할 인자
            trace_id: LangFuse trace_id (X-LF-Trace-ID 헤더)
            observation_id: LangFuse observation_id (X-LF-Parent-Id 헤더)

        Returns:
            도구 실행 결과
        """
        ...


class MockToolClient:
    """Mock Tool Client 구현 (AC 2.4.2, AC 2.4.3).

    개발 및 테스트용 Mock 클라이언트.
    하드코딩된 샘플 도구 목록과 실행 결과를 반환합니다.
    """

    def __init__(self) -> None:
        """Mock Tool Client 초기화."""
        # 하드코딩된 샘플 도구 목록 (AC 2.4.2)
        self._tools: list[ToolDefinition] = [
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

        # 하드코딩된 도구 실행 결과 (AC 2.4.3)
        self._mock_results: dict[str, dict] = {
            "get_weather": {
                "서울": {"temperature": 5, "condition": "맑음", "humidity": 45},
                "부산": {"temperature": 8, "condition": "흐림", "humidity": 60},
                "제주": {"temperature": 10, "condition": "비", "humidity": 80},
            },
        }

    async def list_tools(
        self,
        trace_id: str | None = None,
        observation_id: str | None = None,
    ) -> list[ToolDefinition]:
        """사용 가능한 도구 목록 조회 (Mock 구현).

        Args:
            trace_id: LangFuse trace_id (Mock에서는 무시됨)
            observation_id: LangFuse observation_id (Mock에서는 무시됨)

        Returns:
            하드코딩된 샘플 도구 목록
        """
        return self._tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        trace_id: str | None = None,
        observation_id: str | None = None,
    ) -> ToolResult:
        """도구 실행 (Mock 구현).

        Args:
            tool_name: 실행할 도구 이름
            arguments: 도구에 전달할 인자

        Returns:
            하드코딩된 실행 결과
        """
        # 도구 존재 여부 확인
        tool_names = [t.name for t in self._tools]
        if tool_name not in tool_names:
            return ToolResult(
                success=False,
                result=None,
                error=f"Unknown tool: {tool_name}",
            )

        # 도구별 Mock 응답 처리
        if tool_name == "get_weather":
            location = arguments.get("location")
            # Required argument 체크
            if not location:
                return ToolResult(
                    success=False,
                    result=None,
                    error="Missing required argument: location",
                )
            weather_data = self._mock_results["get_weather"]
            result = weather_data.get(
                location,
                {"temperature": 15, "condition": "알 수 없음", "humidity": 50},
            )
            return ToolResult(success=True, result=result, error=None)

        elif tool_name == "calculate":
            expression = arguments.get("expression")
            # Required argument 체크
            if not expression:
                return ToolResult(
                    success=False,
                    result=None,
                    error="Missing required argument: expression",
                )
            # Mock: 간단한 계산 결과 반환
            return ToolResult(
                success=True,
                result={"expression": expression, "result": "mock_result"},
                error=None,
            )

        # 기본 응답
        return ToolResult(success=True, result={}, error=None)


class ToolClient:
    """Real Tool Client (AC 2.4.4).

    실제 Tool 서버와 통신하는 클라이언트.
    httpx.AsyncClient를 사용하여 비동기 HTTP 통신을 수행합니다.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """Tool Client 초기화.

        Args:
            base_url: Tool 서버 기본 URL. None이면 설정에서 로드.
            timeout: 요청 타임아웃(초). None이면 설정에서 로드.
        """
        settings = get_settings()
        self.base_url = base_url or settings.TOOL_BASE_URL
        self.timeout = timeout or settings.TOOL_TIMEOUT
        self._client: httpx.AsyncClient | None = None
        self._client_lock = Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 인스턴스 반환 (Lazy 초기화, Thread-safe).

        Returns:
            httpx.AsyncClient 인스턴스

        Raises:
            BusinessException: HTTP 클라이언트 생성 실패 시
        """
        async with self._client_lock:
            if self._client is None:
                try:
                    self._client = httpx.AsyncClient(
                        base_url=self.base_url,
                        timeout=self.timeout,
                    )
                except Exception as e:
                    raise BusinessException(
                        ErrorCode.TOOL_EXECUTION,
                        detail=f"HTTP 클라이언트 초기화 실패: {e}",
                    ) from e
        return self._client

    async def list_tools(
        self,
        trace_id: str | None = None,
        observation_id: str | None = None,
    ) -> list[ToolDefinition]:
        """사용 가능한 도구 목록 조회 (AC 2.8.9).

        GET {TOOL_BASE_URL}/v1/tools

        Args:
            trace_id: LangFuse trace_id (X-LF-Trace-ID 헤더)
            observation_id: LangFuse observation_id (X-LF-Parent-Id 헤더)

        Returns:
            도구 정의 목록

        Raises:
            BusinessException: Tool 서버 호출 실패 시
        """
        client = await self._get_client()
        headers: dict[str, str] = {"X-TOL-Scope": "agent"}
        if trace_id:
            headers["X-LF-Trace-ID"] = trace_id
        if observation_id:
            headers["X-LF-Parent-Id"] = observation_id

        try:
            response = await client.get("/v1/tools", headers=headers)
            response.raise_for_status()
            data = response.json()

            tools_data = data.get("data", {}).get("tools", [])
            tools = []
            for t in tools_data:
                # OpenAI function calling 포맷: {type, function: {name, description, parameters}}
                func = t.get("function", t)  # function 키가 없으면 flat 구조로 fallback
                tools.append(ToolDefinition(
                    name=func.get("name", ""),
                    description=func.get("description", ""),
                    parameters=func.get("parameters", {}),
                ))
            logger.info("tool_list_received", tools_count=len(tools))
            return tools

        except httpx.TimeoutException as e:
            raise BusinessException(
                ErrorCode.TOOL_EXECUTION, detail=f"Tool 서버 타임아웃: {e}",
            ) from e
        except httpx.ConnectError as e:
            raise BusinessException(
                ErrorCode.TOOL_EXECUTION, detail=f"Tool 서버 연결 실패: {e}",
            ) from e
        except Exception as e:
            raise BusinessException(
                ErrorCode.TOOL_EXECUTION, detail=f"도구 목록 조회 실패: {e}",
            ) from e

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        trace_id: str | None = None,
        observation_id: str | None = None,
    ) -> ToolResult:
        """도구 실행 (AC 2.8.9).

        POST {TOOL_BASE_URL}/v1/{tool_name}

        Args:
            tool_name: 실행할 도구 이름 (엔드포인트 경로)
            arguments: 도구에 전달할 인자
            trace_id: LangFuse trace_id (X-LF-Trace-ID 헤더)
            observation_id: LangFuse observation_id (X-LF-Parent-Id 헤더)

        Returns:
            도구 실행 결과

        Raises:
            BusinessException: Tool 서버 호출 실패 시
        """
        client = await self._get_client()
        headers: dict[str, str] = {"X-TOL-Scope": "agent"}
        if trace_id:
            headers["X-LF-Trace-ID"] = trace_id
        if observation_id:
            headers["X-LF-Parent-Id"] = observation_id

        try:
            response = await client.post(
                f"/v1/{tool_name}",
                json=arguments,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            result_data = data.get("data", {})
            logger.info("tool_execution_completed", tool_name=tool_name)
            return ToolResult(success=True, result=result_data, error=None)

        except httpx.TimeoutException as e:
            raise BusinessException(
                ErrorCode.TOOL_EXECUTION, detail=f"Tool 서버 타임아웃: {e}",
            ) from e
        except httpx.ConnectError as e:
            raise BusinessException(
                ErrorCode.TOOL_EXECUTION, detail=f"Tool 서버 연결 실패: {e}",
            ) from e
        except Exception as e:
            raise BusinessException(
                ErrorCode.TOOL_EXECUTION, detail=f"도구 실행 실패: {e}",
            ) from e

    async def close(self) -> None:
        """HTTP 클라이언트 연결 종료."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "ToolClient":
        """Context Manager 진입."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context Manager 종료 - 리소스 자동 정리."""
        await self.close()


def get_tool_client() -> MockToolClient | ToolClient:
    """Tool Client 팩토리 함수 (AC 2.4.5).

    Settings의 USE_MOCK_TOOL 설정에 따라 적절한 클라이언트를 반환합니다.

    Returns:
        USE_MOCK_TOOL=True: MockToolClient
        USE_MOCK_TOOL=False: ToolClient
    """
    settings = get_settings()

    if settings.USE_MOCK_TOOL:
        return MockToolClient()

    return ToolClient(
        base_url=settings.TOOL_BASE_URL,
        timeout=settings.TOOL_TIMEOUT,
    )
