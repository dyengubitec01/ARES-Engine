"""Tests for Story 2.1: LangGraph 기본 워크플로우 구조 설정."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.workflows.main_agent import (
    build_graph,
    compile_graph,
    create_initial_state,
    get_compiled_graph,
    run_workflow,
)
from app.workflows.main_agent.nodes import rewriter, synthesizer


class TestAgentState:
    """Tests for AC 2.1.1: AgentState 정의."""

    def test_create_initial_state_required_fields(self) -> None:
        """Test initial state creation with required fields."""
        state = create_initial_state(
            query="테스트 질문",
            session_id="test-session-123",
        )

        assert state["query"] == "테스트 질문"
        assert state["session_id"] == "test-session-123"
        assert state["history"] == []

    def test_create_initial_state_with_history(self) -> None:
        """Test initial state creation with history."""
        history = [
            {"role": "user", "content": "이전 질문"},
            {"role": "assistant", "content": "이전 답변"},
        ]
        state = create_initial_state(
            query="후속 질문",
            session_id="test-session-123",
            history=history,
        )

        assert state["history"] == history
        assert len(state["history"]) == 2

    def test_initial_state_default_values(self) -> None:
        """Test initial state has correct default values."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )

        assert state["standalone_query"] == ""
        assert state["context"] == []
        assert state["response"] == ""
        assert state["retrieval_status"] == "skipped"
        assert state["thoughts"] == []
        assert state["retry_count"] == 0
        assert state["error"] is None
        assert state["user_depts"] == []
        assert state["excluded_docs"] == []

    def test_create_initial_state_with_user_depts_and_excluded_docs(self) -> None:
        """create_initial_state에 user_depts, excluded_docs 전달 (AC 3.6.1, 3.6.3)."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
            user_depts=["D001", "D002"],
            excluded_docs=["cid-1", "cid-2"],
        )

        assert state["user_depts"] == ["D001", "D002"]
        assert state["excluded_docs"] == ["cid-1", "cid-2"]

    def test_agent_state_fields_documented(self) -> None:
        """Test AgentState TypedDict has expected fields."""
        # TypedDict의 필수 필드 확인
        required_keys = {"query", "history", "session_id"}
        optional_keys = {
            "standalone_query",
            "context",
            "response",
            "thoughts",
            "retry_count",
            "error",
        }

        state = create_initial_state(query="test", session_id="123")
        state_keys = set(state.keys())

        assert required_keys.issubset(state_keys)
        assert optional_keys.issubset(state_keys)


class TestRewriterNode:
    """Tests for rewriter node (AC 2.1.2, 2.1.4, 2.1.5)."""

    @pytest.mark.asyncio
    async def test_rewriter_returns_standalone_query(self) -> None:
        """Test rewriter node returns standalone_query."""
        state = create_initial_state(
            query="그것의 가격은?",
            session_id="test-123",
        )

        result = await rewriter(state)

        assert "standalone_query" in result
        assert isinstance(result["standalone_query"], str)

    @pytest.mark.asyncio
    async def test_rewriter_updates_thoughts(self) -> None:
        """Test rewriter node updates thoughts field (AC 2.1.5)."""
        state = create_initial_state(
            query="테스트 질문",
            session_id="test-123",
        )

        result = await rewriter(state)

        assert "thoughts" in result
        assert len(result["thoughts"]) > 0
        assert isinstance(result["thoughts"][0], str)

    @pytest.mark.asyncio
    async def test_rewriter_with_history(self) -> None:
        """Test rewriter with conversation history."""
        from unittest.mock import patch

        from langchain_core.messages import AIMessage

        history = [{"role": "user", "content": "갤럭시 S24에 대해 알려줘"}]
        state = create_initial_state(
            query="그것의 가격은?",
            session_id="test-123",
            history=history,
        )

        mock_response = AIMessage(content="갤럭시 S24의 가격은 얼마인가요?")

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_with_failover = AsyncMock(return_value=mock_response)
            result = await rewriter(state)

        # Story 2.2: 이력이 있으면 "대화 맥락을 반영" 메시지
        assert "대화 맥락" in result["thoughts"][0]


class TestSynthesizerNode:
    """Tests for synthesizer node (AC 2.1.2, 2.1.4, 2.1.5)."""

    @pytest.mark.asyncio
    async def test_synthesizer_returns_response(self) -> None:
        """Test synthesizer node returns response."""
        state = create_initial_state(
            query="테스트 질문",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트 질문"

        # synthesizer requires config for streaming LLM calls
        result = await synthesizer(state, config={})

        assert "response" in result
        assert isinstance(result["response"], str)
        assert len(result["response"]) > 0

    @pytest.mark.asyncio
    async def test_synthesizer_updates_thoughts(self) -> None:
        """Test synthesizer node updates thoughts field (AC 2.1.5)."""
        state = create_initial_state(
            query="테스트 질문",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트 질문"

        result = await synthesizer(state, config={})

        assert "thoughts" in result
        assert len(result["thoughts"]) > 0

    @pytest.mark.asyncio
    async def test_synthesizer_with_context(self) -> None:
        """Test synthesizer with context documents (Story 2.5: LLM 기반)."""

        state = create_initial_state(
            query="테스트 질문",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트 질문"
        state["context"] = ["문서1 내용", "문서2 내용"]

        from tests.test_retriever_synthesizer import FakeStreamingLLM

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = FakeStreamingLLM("테스트 답변입니다.")

            result = await synthesizer(state, config={})

            assert "2개 문서" in result["thoughts"][-1]


class TestStateGraph:
    """Tests for AC 2.1.2, 2.1.3: StateGraph 기본 구조."""

    def test_build_graph_returns_state_graph(self) -> None:
        """Test build_graph returns StateGraph instance."""
        graph = build_graph()

        assert graph is not None
        # StateGraph는 nodes 속성을 가짐
        assert hasattr(graph, "nodes")

    def test_graph_has_required_nodes(self) -> None:
        """Test graph has rewriter and synthesizer nodes."""
        graph = build_graph()

        # 노드 이름 확인
        node_names = set(graph.nodes.keys())
        assert "rewriter" in node_names
        assert "synthesizer" in node_names

    def test_compile_graph_returns_runnable(self) -> None:
        """Test compile_graph returns compiled runnable."""
        compiled = compile_graph()

        # CompiledStateGraph는 ainvoke 메서드를 가짐
        assert hasattr(compiled, "ainvoke")
        assert hasattr(compiled, "invoke")

    def test_get_compiled_graph_singleton(self) -> None:
        """Test get_compiled_graph returns same instance."""
        graph1 = get_compiled_graph()
        graph2 = get_compiled_graph()

        assert graph1 is graph2


class TestWorkflowExecution:
    """Tests for AC 2.1.3, 2.1.4: 워크플로우 실행 및 상태 전달."""

    @pytest.mark.asyncio
    async def test_run_workflow_basic(self) -> None:
        """Test basic workflow execution."""
        result = await run_workflow(
            query="테스트 질문입니다",
            session_id="test-session-001",
        )

        assert result is not None
        assert "response" in result
        assert "thoughts" in result

    @pytest.mark.asyncio
    async def test_run_workflow_state_passing(self) -> None:
        """Test state is passed between nodes (AC 2.1.4)."""
        result = await run_workflow(
            query="테스트 질문",
            session_id="test-123",
        )

        # rewriter가 설정한 standalone_query가 synthesizer에 전달됨
        assert result["standalone_query"] != ""
        # 최종 response가 생성됨
        assert result["response"] != ""

    @pytest.mark.asyncio
    async def test_run_workflow_thoughts_accumulated(self) -> None:
        """Test thoughts are accumulated across nodes (AC 2.1.5)."""
        result = await run_workflow(
            query="테스트 질문",
            session_id="test-123",
        )

        # 최소 2개의 thoughts (rewriter + synthesizer)
        assert len(result["thoughts"]) >= 2

    @pytest.mark.asyncio
    async def test_run_workflow_with_history(self) -> None:
        """Test workflow execution with conversation history."""
        history = [
            {"role": "user", "content": "첫 번째 질문"},
            {"role": "assistant", "content": "첫 번째 답변"},
        ]

        result = await run_workflow(
            query="후속 질문입니다",
            session_id="test-session-002",
            history=history,
        )

        assert result["history"] == history
        assert len(result["thoughts"]) >= 2

    @pytest.mark.asyncio
    async def test_run_workflow_preserves_session_id(self) -> None:
        """Test session_id is preserved through workflow."""
        session_id = "unique-session-12345"

        result = await run_workflow(
            query="테스트",
            session_id=session_id,
        )

        assert result["session_id"] == session_id


class TestErrorHandling:
    """Tests for AC 2.1.6: 에러 처리."""

    def test_initial_state_error_is_none(self) -> None:
        """Test initial state has error=None."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )

        assert state["error"] is None
        assert state["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_workflow_completes_without_error(self) -> None:
        """Test successful workflow has no error."""
        result = await run_workflow(
            query="정상 질문",
            session_id="test-123",
        )

        assert result["error"] is None
        assert result["retry_count"] == 0


class TestNegativeCases:
    """Negative tests - 비정상 입력에 대한 에러 처리 검증."""

    @pytest.mark.asyncio
    async def test_empty_query_raises_error(self) -> None:
        """Test empty query raises ValueError."""
        with pytest.raises(ValueError, match="query cannot be empty"):
            await run_workflow(query="", session_id="test-123")

    @pytest.mark.asyncio
    async def test_whitespace_query_raises_error(self) -> None:
        """Test whitespace-only query raises ValueError."""
        with pytest.raises(ValueError, match="query cannot be empty"):
            await run_workflow(query="   ", session_id="test-123")

    @pytest.mark.asyncio
    async def test_empty_session_id_raises_error(self) -> None:
        """Test empty session_id raises ValueError."""
        with pytest.raises(ValueError, match="session_id cannot be empty"):
            await run_workflow(query="테스트 질문", session_id="")

    @pytest.mark.asyncio
    async def test_whitespace_session_id_raises_error(self) -> None:
        """Test whitespace-only session_id raises ValueError."""
        with pytest.raises(ValueError, match="session_id cannot be empty"):
            await run_workflow(query="테스트 질문", session_id="  ")

    @pytest.mark.asyncio
    async def test_long_query_handled(self) -> None:
        """Test very long query is handled properly."""
        long_query = "테스트 " * 500  # 약 2000자
        result = await run_workflow(
            query=long_query,
            session_id="test-123",
        )

        assert result["query"] == long_query
        assert result["response"] != ""

    @pytest.mark.asyncio
    async def test_unicode_query_handled(self) -> None:
        """Test query with special unicode characters."""
        unicode_query = "이모지 테스트 🎉🚀 특수문자 ★☆♠♣"
        result = await run_workflow(
            query=unicode_query,
            session_id="test-123",
        )

        assert result["query"] == unicode_query
        assert result["response"] != ""
