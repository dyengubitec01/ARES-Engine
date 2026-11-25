"""
Story 2.8 Integration Tests: Intent Router + RAG/Tool 서버 연동.

실제 LLM/RAG/Tool 서버 연결 필수.
pytest tests/integration/test_workflow_routes.py -v -m integration 으로 실행.

테스트 항목:
- RAG 경로: 문서 검색 질문 → retriever → synthesizer
- Tool 경로: 도구 실행 질문 → tool_executor → synthesizer
- Both 경로 (fan-out/fan-in): 병렬 실행 → synthesizer
- State Reducer 병합 검증
"""

import uuid

import httpx
import pytest

from tests.integration.conftest import skip_no_llm


def _rag_server_available() -> bool:
    """RAG 서버 접속 가능 여부."""
    from app.core.config import get_settings

    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.RAG_BASE_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def _tool_server_available() -> bool:
    """Tool 서버 접속 가능 여부."""
    from app.core.config import get_settings

    settings = get_settings()
    try:
        resp = httpx.get(f"{settings.TOOL_BASE_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


skip_no_rag = pytest.mark.skipif(
    not _rag_server_available(),
    reason="RAG server not available",
)

skip_no_tool = pytest.mark.skipif(
    not _tool_server_available(),
    reason="Tool server not available",
)

pytestmark = pytest.mark.integration


@skip_no_llm
@skip_no_rag
class TestRAGRoute:
    """RAG 경로 통합 테스트 (AC 2.8.5)."""

    @pytest.mark.asyncio
    async def test_rag_route_returns_documents(self) -> None:
        """RAG 경로: 문서 검색 질문 → retriever → synthesizer."""
        from app.workflows.main_agent.graph import run_workflow

        session_id = f"integ-rag-{uuid.uuid4().hex[:8]}"
        result = await run_workflow(
            query="사내문서에서 휴가 규정 찾아줘",
            session_id=session_id,
        )

        assert result.get("route") == "rag"
        assert len(result.get("context", [])) > 0, "RAG should return context"
        assert len(result.get("sources", [])) > 0, "RAG should return sources"
        assert result.get("response"), "Should generate response"

    @pytest.mark.asyncio
    async def test_rag_route_thoughts_chain(self) -> None:
        """RAG 경로: thoughts가 순서대로 누적되는지 확인."""
        from app.workflows.main_agent.graph import run_workflow

        session_id = f"integ-rag-thoughts-{uuid.uuid4().hex[:8]}"
        result = await run_workflow(
            query="RAG노드사용 문서 검색해줘",
            session_id=session_id,
        )

        thoughts = result.get("thoughts", [])
        assert len(thoughts) >= 3, f"Expected >= 3 thoughts (rewriter+router+retriever+synthesizer), got {len(thoughts)}"


@skip_no_llm
@skip_no_tool
class TestToolRoute:
    """Tool 경로 통합 테스트 (AC 2.8.4)."""

    @pytest.mark.asyncio
    async def test_tool_route_executes_summary(self) -> None:
        """Tool 경로: 도구 실행 질문 → tool_executor → synthesizer."""
        from app.workflows.main_agent.graph import run_workflow

        session_id = f"integ-tool-{uuid.uuid4().hex[:8]}"
        result = await run_workflow(
            query="TOOL노드사용 대화 요약해줘",
            session_id=session_id,
            history=[
                {"role": "user", "content": "안녕하세요"},
                {"role": "assistant", "content": "안녕하세요! 무엇을 도와드릴까요?"},
            ],
        )

        route = result.get("route")
        assert route in ("tool", "both"), f"Expected tool or both route, got {route}"

        context = result.get("context", [])
        tool_results = [c for c in context if "[도구 결과" in c]
        assert len(tool_results) > 0, "Tool executor should add tool result to context"
        assert result.get("response"), "Should generate response"


@skip_no_llm
@skip_no_rag
@skip_no_tool
class TestBothRoute:
    """Both(fan-out/fan-in) 경로 통합 테스트 (AC 2.8.6)."""

    @pytest.mark.asyncio
    async def test_fanout_parallel_execution(self) -> None:
        """Both 경로: RAG + Tool 병렬 실행 후 synthesizer에서 합류."""
        from app.workflows.main_agent.graph import run_workflow

        session_id = f"integ-both-{uuid.uuid4().hex[:8]}"
        result = await run_workflow(
            query="TOOL노드사용 대화 요약하고 관련 문서도 찾아줘",
            session_id=session_id,
            history=[
                {"role": "user", "content": "프로젝트 일정 논의"},
                {"role": "assistant", "content": "프로젝트 일정을 확인하겠습니다."},
            ],
        )

        route = result.get("route")
        context = result.get("context", [])

        if route == "both":
            # fan-out/fan-in 검증: RAG 문서 + Tool 결과 모두 존재
            rag_items = [c for c in context if c.startswith("<document")]
            tool_items = [c for c in context if "[도구 결과" in c]
            assert len(rag_items) > 0, "Both route should have RAG documents"
            assert len(tool_items) > 0, "Both route should have tool results"

            # State Reducer 병합 검증: context 총 개수 = RAG + Tool
            assert len(context) == len(rag_items) + len(tool_items)
        else:
            # LLM이 both 대신 단일 경로 선택한 경우 (LLM 판단이라 허용)
            assert len(context) > 0, f"Route {route} should still produce context"

        assert result.get("response"), "Should generate response"

    @pytest.mark.asyncio
    async def test_state_reducer_merges_thoughts(self) -> None:
        """State Reducer: 병렬 노드의 thoughts가 올바르게 병합되는지 확인."""
        from app.workflows.main_agent.graph import run_workflow

        session_id = f"integ-reducer-{uuid.uuid4().hex[:8]}"
        result = await run_workflow(
            query="TOOL노드사용 요약해주고 사내 규정도 검색해줘",
            session_id=session_id,
            history=[
                {"role": "user", "content": "테스트"},
                {"role": "assistant", "content": "네"},
            ],
        )

        thoughts = result.get("thoughts", [])
        route = result.get("route")

        if route == "both":
            # both 경로: rewriter + router + retriever + tool_executor + synthesizer = 5
            assert len(thoughts) >= 5, f"Both route should have >= 5 thoughts, got {len(thoughts)}: {thoughts}"
        else:
            # 단일 경로: rewriter + router + (retriever|tool_executor) + synthesizer = 4
            assert len(thoughts) >= 3, f"Should have >= 3 thoughts, got {len(thoughts)}"
