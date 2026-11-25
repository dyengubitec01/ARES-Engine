"""
LangFuse Integration Tests.

실제 LangFuse 서버에 트레이스가 찍히는지 확인하는 통합 테스트.
pytest -m integration 으로 실행.

필수 조건:
- LangFuse 서버 실행 중 (docker-compose)
- .env에 LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY 설정
- LLM 서버 실행 중

Cross-service trace_id 검증 (TestCrossServiceTraceId):
- Agent 워크플로우 → RAG/Tool 서버로 X-LF-Trace-ID 헤더 전달 확인
- LLM + LangFuse + RAG/Tool 서버 모두 실행 필요
"""

import uuid
from unittest.mock import patch

import httpx
import pytest

from app.core.config import settings
from tests.integration.conftest import (
    skip_no_langfuse,
    skip_no_llm,
    skip_no_rag,
    skip_no_tool,
)

# Integration 테스트 마커
pytestmark = pytest.mark.integration


@skip_no_langfuse
class TestLangFuseConnection:
    """LangFuse 연결 테스트."""

    def test_langfuse_settings_loaded(self) -> None:
        """LangFuse 설정이 로드되었는지 확인."""
        assert settings.LANGFUSE_PUBLIC_KEY is not None
        assert settings.LANGFUSE_SECRET_KEY is not None
        assert settings.LANGFUSE_HOST is not None
        print(f"\nLangFuse Host: {settings.LANGFUSE_HOST}")

    def test_tracing_manager_enabled(self) -> None:
        """TracingManager가 활성화되었는지 확인."""
        from app.core.tracing import TracingManager

        manager = TracingManager()
        manager.initialize()

        assert manager.enabled is True, "LangFuse tracing should be enabled"

    def test_callback_handler_created(self) -> None:
        """CallbackHandler가 생성되는지 확인."""
        from app.core.tracing import TracingManager

        manager = TracingManager()
        handler = manager.get_callback_handler()

        assert handler is not None, "CallbackHandler should be created"


@skip_no_langfuse
@skip_no_llm
class TestLangFuseTracing:
    """실제 LLM 호출 + LangFuse 트레이싱 테스트."""

    @pytest.mark.asyncio
    async def test_llm_invoke_traced(self) -> None:
        """LLM 호출이 LangFuse에 트레이스되는지 확인."""
        from langchain_core.messages import HumanMessage

        from app.core.llm_factory import llm_factory

        session_id = f"integration-test-{uuid.uuid4().hex[:8]}"
        print(f"\n[LangFuse] Session ID: {session_id}")
        print(f"[LangFuse] Check traces at: {settings.LANGFUSE_HOST}")

        messages = [HumanMessage(content="Say 'Hello' in Korean. One word only.")]

        response = await llm_factory.invoke_with_failover(
            role="fast",
            messages=messages,
            session_id=session_id,
            request_type="integration_test",
            trace_metadata={"test": "llm_invoke_traced"},
        )

        assert response is not None
        assert response.content is not None
        print(f"[LLM Response] {response.content}")

    @pytest.mark.asyncio
    async def test_query_rewriter_traced(self) -> None:
        """Query Rewriter가 LangFuse에 트레이스되는지 확인."""
        from app.workflows.main_agent import create_initial_state
        from app.workflows.main_agent.nodes.rewriter import rewriter

        session_id = f"rewriter-test-{uuid.uuid4().hex[:8]}"
        print(f"\n[LangFuse] Session ID: {session_id}")
        print(f"[LangFuse] Check traces at: {settings.LANGFUSE_HOST}")

        # 히스토리가 있는 케이스 - LLM 호출 발생
        state = create_initial_state(
            query="그거 얼마야?",
            session_id=session_id,
            history=[
                {"role": "user", "content": "갤럭시 S24에 대해 알려줘"},
                {"role": "assistant", "content": "갤럭시 S24는 삼성의 최신 스마트폰입니다."},
            ],
        )

        result = await rewriter(state)

        assert result is not None
        assert "standalone_query" in result
        assert "thoughts" in result
        print("[Original Query] 그거 얼마야?")
        print(f"[Standalone Query] {result['standalone_query']}")
        print(f"[Thoughts] {result['thoughts']}")

    @pytest.mark.asyncio
    async def test_full_workflow_traced(self) -> None:
        """전체 워크플로우가 LangFuse에 트레이스되는지 확인."""
        from app.workflows.main_agent.graph import run_workflow

        session_id = f"workflow-test-{uuid.uuid4().hex[:8]}"
        print(f"\n[LangFuse] Session ID: {session_id}")
        print(f"[LangFuse] Check traces at: {settings.LANGFUSE_HOST}")

        final_state = await run_workflow(
            query="안녕하세요",
            session_id=session_id,
            history=[],
        )

        assert final_state is not None
        assert "standalone_query" in final_state
        print(f"[Final State] standalone_query: {final_state.get('standalone_query')}")
        print(f"[Final State] response: {final_state.get('response', 'N/A')}")
        print(f"[Final State] context count: {len(final_state.get('context', []))}")
        print(f"[Final State] thoughts: {final_state.get('thoughts', [])}")


@skip_no_langfuse
@skip_no_llm
class TestLangFuseMetadata:
    """LangFuse 메타데이터 트레이싱 테스트."""

    @pytest.mark.asyncio
    async def test_session_id_in_trace(self) -> None:
        """session_id가 트레이스에 포함되는지 확인."""
        from langchain_core.messages import HumanMessage

        from app.core.llm_factory import llm_factory

        session_id = f"metadata-test-{uuid.uuid4().hex[:8]}"
        user_id = "test-user-001"

        print(f"\n[LangFuse] Session ID: {session_id}")
        print(f"[LangFuse] User ID: {user_id}")

        messages = [HumanMessage(content="Hi")]

        response = await llm_factory.invoke_with_failover(
            role="fast",
            messages=messages,
            session_id=session_id,
            user_id=user_id,
            request_type="metadata_test",
            trace_metadata={
                "custom_field": "custom_value",
                "test_type": "metadata_verification",
            },
        )

        assert response is not None
        print(f"[Response] {response.content}")
        print("[Check LangFuse UI for session_id, user_id, and metadata fields]")


@skip_no_langfuse
@skip_no_llm
@skip_no_rag
class TestCrossServiceTraceId:
    """Cross-service trace_id 전달 검증.

    Agent 워크플로우 실행 시 LangFuse trace_id가
    RAG/Tool 서버에 X-LF-Trace-ID 헤더로 전달되는지 확인.

    검증 항목:
    1. extract_trace_context()가 non-None trace_id/observation_id를 반환하는지
    2. RAG/Tool 서버 HTTP 요청에 X-LF-Trace-ID 헤더가 포함되는지
    3. LangFuse UI에서 동일 trace_id로 cross-service 트레이스 확인 가능

    주의: USE_MOCK_RAG/USE_MOCK_TOOL을 False로 패치하여 실제 서버 연동.
    """

    @pytest.mark.asyncio
    async def test_rag_route_headers(self) -> None:
        """RAG 경로: X-LF-Trace-ID + X-LF-Parent-Id 헤더가 RAG 서버에 전달되는지 확인."""
        from app.workflows.main_agent.graph import run_workflow
        from app.workflows.shared.tracing_utils import (
            extract_trace_context as real_extract,
        )

        captured_contexts = []
        captured_headers = []

        def spy_extract(config):
            ctx = real_extract(config)
            captured_contexts.append(ctx)
            return ctx

        original_post = httpx.AsyncClient.post

        async def spy_post(self, url, **kwargs):
            headers = kwargs.get("headers", {})
            if "X-LF-Trace-ID" in headers:
                captured_headers.append({
                    "url": url,
                    "trace_id": headers["X-LF-Trace-ID"],
                    "parent_id": headers.get("X-LF-Parent-Id"),
                })
            return await original_post(self, url, **kwargs)

        session_id = f"trace-rag-{uuid.uuid4().hex[:8]}"
        print(f"\n[Cross-Service Trace] session_id: {session_id}")

        with patch(
            "app.workflows.main_agent.nodes.retriever.extract_trace_context",
            side_effect=spy_extract,
        ), patch.object(
            httpx.AsyncClient, "post", spy_post,
        ), patch.object(
            settings, "USE_MOCK_RAG", False,
        ):
            result = await run_workflow(
                query="사내문서에서 휴가 규정 찾아줘",
                session_id=session_id,
                user_id="trace-tester",
            )

        route = result.get("route")
        print(f"[Route] {route}")
        assert result.get("response"), "Should produce response"

        if route in ("rag", "both"):
            assert len(captured_contexts) > 0, "extract_trace_context should be called"
            ctx = captured_contexts[0]
            assert ctx.trace_id is not None, "trace_id should not be None"
            assert ctx.observation_id is not None, "observation_id should not be None"
            print(f"[TraceContext] trace_id={ctx.trace_id}, observation_id={ctx.observation_id}")

            rag_headers = [h for h in captured_headers if "/v1/search" in h["url"]]
            assert len(rag_headers) > 0, "Headers should be sent to RAG server"
            assert rag_headers[0]["trace_id"] == ctx.trace_id
            assert rag_headers[0]["parent_id"] == ctx.observation_id
            print(f"[Header] X-LF-Trace-ID: {rag_headers[0]['trace_id']}")
            print(f"[Header] X-LF-Parent-Id: {rag_headers[0]['parent_id']}")
        else:
            print(f"[Info] LLM chose '{route}' route, RAG headers not verified")

        print(f"[LangFuse] Verify at: {settings.LANGFUSE_HOST}")

    @pytest.mark.asyncio
    @skip_no_tool
    async def test_tool_route_headers(self) -> None:
        """Tool 경로: X-LF-Trace-ID + X-LF-Parent-Id 헤더가 Tool 서버에 전달되는지 확인."""
        from app.workflows.main_agent.graph import run_workflow
        from app.workflows.shared.tracing_utils import (
            extract_trace_context as real_extract,
        )

        captured_contexts = []
        captured_headers = []

        def spy_extract(config):
            ctx = real_extract(config)
            captured_contexts.append(ctx)
            return ctx

        original_post = httpx.AsyncClient.post
        original_get = httpx.AsyncClient.get

        async def spy_post(self, url, **kwargs):
            headers = kwargs.get("headers", {})
            if "X-LF-Trace-ID" in headers:
                captured_headers.append({
                    "url": url,
                    "trace_id": headers["X-LF-Trace-ID"],
                    "parent_id": headers.get("X-LF-Parent-Id"),
                    "method": "POST",
                })
            return await original_post(self, url, **kwargs)

        async def spy_get(self, url, **kwargs):
            headers = kwargs.get("headers", {})
            if "X-LF-Trace-ID" in headers:
                captured_headers.append({
                    "url": url,
                    "trace_id": headers["X-LF-Trace-ID"],
                    "parent_id": headers.get("X-LF-Parent-Id"),
                    "method": "GET",
                })
            return await original_get(self, url, **kwargs)

        session_id = f"trace-tool-{uuid.uuid4().hex[:8]}"
        print(f"\n[Cross-Service Trace] session_id: {session_id}")

        with patch(
            "app.workflows.main_agent.nodes.tool_executor.extract_trace_context",
            side_effect=spy_extract,
        ), patch.object(
            httpx.AsyncClient, "post", spy_post,
        ), patch.object(
            httpx.AsyncClient, "get", spy_get,
        ), patch.object(
            settings, "USE_MOCK_TOOL", False,
        ):
            result = await run_workflow(
                query="TOOL노드사용 대화 요약해줘",
                session_id=session_id,
                user_id="trace-tester",
                history=[
                    {"role": "user", "content": "프로젝트 일정 논의"},
                    {"role": "assistant", "content": "프로젝트 일정을 확인하겠습니다."},
                ],
            )

        route = result.get("route")
        print(f"[Route] {route}")
        assert result.get("response"), "Should produce response"

        if route in ("tool", "both"):
            assert len(captured_contexts) > 0, "extract_trace_context should be called"
            ctx = captured_contexts[0]
            assert ctx.trace_id is not None, "trace_id should not be None"
            assert ctx.observation_id is not None, "observation_id should not be None"
            print(f"[TraceContext] trace_id={ctx.trace_id}, observation_id={ctx.observation_id}")

            tool_headers = [h for h in captured_headers if "/v1/" in h["url"]]
            assert len(tool_headers) > 0, "Headers should be sent to Tool server"
            for h in tool_headers:
                assert h["trace_id"] == ctx.trace_id
                assert h["parent_id"] == ctx.observation_id
                print(f"[Header] {h['method']} {h['url']} → trace_id={h['trace_id']}, parent_id={h['parent_id']}")
        else:
            print(f"[Info] LLM chose '{route}' route, Tool headers not verified")

        print(f"[LangFuse] Verify at: {settings.LANGFUSE_HOST}")
