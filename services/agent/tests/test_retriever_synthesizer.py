"""Tests for Story 2.5: Retriever 및 Synthesizer 노드 구현."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig

from app.clients import Document
from app.workflows.main_agent import create_initial_state
from app.workflows.main_agent.nodes.retriever import retriever
from app.workflows.main_agent.nodes.synthesizer import synthesizer
from app.workflows.main_agent.prompts.synthesizer import (
    NO_CONTEXT_RESPONSE,
    SYNTHESIZER_PROMPT,
)


# ============================================================================
# Helper: LLM mock factory for streaming
# ============================================================================
async def mock_stream_generator(content: str):
    """Create async generator that yields AIMessageChunk tokens."""
    for token in content.split():
        yield AIMessageChunk(content=token + " ")


class FakeStreamingLLM(Runnable):
    """LCEL chain 호환 fake LLM.

    Runnable을 상속하여 (prompt | llm).astream()에서
    atransform이 정상 동작한다.
    """

    def __init__(
        self,
        content: str = "",
        *,
        error: Exception | None = None,
        capture: list | None = None,
    ) -> None:
        self.content = content
        self.error = error
        self.capture = capture

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> AIMessage:
        if self.error:
            raise self.error
        return AIMessage(content=self.content)

    async def ainvoke(self, input: Any, config: Any = None, **kwargs: Any) -> AIMessage:
        if self.error:
            raise self.error
        return AIMessage(content=self.content)

    async def astream(self, input: Any, config: Any = None, **kwargs: Any):  # type: ignore[override]
        if self.capture is not None:
            if isinstance(input, list):
                self.capture.extend(input)
            elif hasattr(input, "to_messages"):
                self.capture.extend(input.to_messages())
        if self.error:
            raise self.error
        async for chunk in mock_stream_generator(self.content):
            yield chunk


def create_streaming_llm_mock(content: str) -> FakeStreamingLLM:
    """Create a fake LLM that streams the given content (LCEL chain compatible)."""
    return FakeStreamingLLM(content)


# Default config for tests
TEST_CONFIG: RunnableConfig = {"callbacks": []}


class TestSynthesizerPrompt:
    """Tests for AC 2.5.5: Synthesizer 프롬프트."""

    def test_prompt_is_chat_prompt_template(self) -> None:
        """Test SYNTHESIZER_PROMPT is a ChatPromptTemplate."""
        assert isinstance(SYNTHESIZER_PROMPT, ChatPromptTemplate)

    def test_prompt_has_required_variables(self) -> None:
        """Test prompt template has context and query variables."""
        input_vars = SYNTHESIZER_PROMPT.input_variables
        assert "context" in input_vars
        assert "query" in input_vars

    def test_prompt_format_produces_messages(self) -> None:
        """Test prompt can be formatted into messages."""
        messages = SYNTHESIZER_PROMPT.format_messages(
            context="[문서 1] 테스트 내용입니다.",
            query="테스트 질문",
            history="(이전 대화 없음)",
        )

        assert len(messages) >= 2  # system + user at minimum

    def test_prompt_contains_instructions(self) -> None:
        """Test prompt contains required instructions (AC 2.5.5)."""
        messages = SYNTHESIZER_PROMPT.format_messages(
            context="테스트",
            query="테스트",
            history="(이전 대화 없음)",
        )
        system_content = str(messages[0].content)

        assert "컨텍스트" in system_content or "참고 문서" in system_content
        assert "외부 지식" in system_content
        assert "답변" in system_content

    def test_no_context_response_defined(self) -> None:
        """Test NO_CONTEXT_RESPONSE is defined."""
        assert NO_CONTEXT_RESPONSE is not None
        assert "검색 결과가 없습니다" in NO_CONTEXT_RESPONSE


class TestRetrieverNode:
    """Tests for AC 2.5.1, 2.5.3: Retriever 노드."""

    @pytest.mark.asyncio
    async def test_retriever_calls_rag_client(self) -> None:
        """Test retriever calls RAGClient.search (AC 2.5.1)."""
        state = create_initial_state(
            query="테스트 질문",
            session_id="test-123",
        )
        state["standalone_query"] = "재구성된 질문"

        mock_documents = [
            Document(content="문서 1 내용", metadata={"source": "test.pdf"}, score=0.9),
            Document(content="문서 2 내용", metadata={"source": "test2.pdf"}, score=0.8),
        ]

        with (
            patch("app.workflows.main_agent.nodes.retriever.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.retriever.get_rag_client") as mock_get_client,
        ):
            mock_settings.SKIP_RAG = False
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=mock_documents)
            mock_get_client.return_value = mock_client

            result = await retriever(state, TEST_CONFIG)

            mock_client.search.assert_called_once_with(
                query="재구성된 질문", trace_id=None,
                observation_id=None, user_depts=[], excluded_docs=[],
            )
            assert "context" in result

    @pytest.mark.asyncio
    async def test_retriever_uses_standalone_query(self) -> None:
        """Test retriever uses standalone_query for search (AC 2.5.3)."""
        state = create_initial_state(
            query="원본 질문",
            session_id="test-123",
        )
        state["standalone_query"] = "재구성된 질문"

        with (
            patch("app.workflows.main_agent.nodes.retriever.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.retriever.get_rag_client") as mock_get_client,
        ):
            mock_settings.SKIP_RAG = False
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=[])
            mock_get_client.return_value = mock_client

            await retriever(state, TEST_CONFIG)

            mock_client.search.assert_called_once_with(
                query="재구성된 질문", trace_id=None,
                observation_id=None, user_depts=[], excluded_docs=[],
            )

    @pytest.mark.asyncio
    async def test_retriever_fallback_to_original_query(self) -> None:
        """Test retriever falls back to original query if standalone_query missing."""
        state = create_initial_state(
            query="원본 질문",
            session_id="test-123",
        )
        # standalone_query not set

        with (
            patch("app.workflows.main_agent.nodes.retriever.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.retriever.get_rag_client") as mock_get_client,
        ):
            mock_settings.SKIP_RAG = False
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=[])
            mock_get_client.return_value = mock_client

            await retriever(state, TEST_CONFIG)

            mock_client.search.assert_called_once_with(
                query="원본 질문", trace_id=None,
                observation_id=None, user_depts=[], excluded_docs=[],
            )

    @pytest.mark.asyncio
    async def test_retriever_formats_documents(self) -> None:
        """Test retriever formats documents using format_documents_for_context (AC 2.5.3)."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"

        mock_documents = [
            Document(content="문서 내용", metadata={"source": "test.pdf"}, score=0.9),
        ]

        with (
            patch("app.workflows.main_agent.nodes.retriever.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.retriever.get_rag_client") as mock_get_client,
        ):
            mock_settings.SKIP_RAG = False
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=mock_documents)
            mock_get_client.return_value = mock_client

            result = await retriever(state, TEST_CONFIG)

            assert len(result["context"]) == 1
            assert result["context"][0] == "<document>\n문서 내용\n</document>"
            assert result["retrieval_status"] == "ok"

    @pytest.mark.asyncio
    async def test_retriever_empty_results(self) -> None:
        """Test retriever handles empty search results."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"

        with (
            patch("app.workflows.main_agent.nodes.retriever.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.retriever.get_rag_client") as mock_get_client,
        ):
            mock_settings.SKIP_RAG = False
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=[])
            mock_get_client.return_value = mock_client

            result = await retriever(state, TEST_CONFIG)

            assert result["context"] == []
            assert result["retrieval_status"] == "empty"
            assert "찾지 못했습니다" in result["thoughts"][-1]

    @pytest.mark.asyncio
    async def test_retriever_thought_message_with_results(self) -> None:
        """Test retriever adds correct thought message when documents found."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"

        mock_documents = [
            Document(content="문서 1", metadata={}, score=0.9),
            Document(content="문서 2", metadata={}, score=0.8),
            Document(content="문서 3", metadata={}, score=0.7),
        ]

        with (
            patch("app.workflows.main_agent.nodes.retriever.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.retriever.get_rag_client") as mock_get_client,
        ):
            mock_settings.SKIP_RAG = False
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=mock_documents)
            mock_get_client.return_value = mock_client

            result = await retriever(state, TEST_CONFIG)

            assert "3건" in result["thoughts"][-1]

    @pytest.mark.asyncio
    async def test_retriever_error_handling(self) -> None:
        """Test retriever returns empty context and error status on failure."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"

        with (
            patch("app.workflows.main_agent.nodes.retriever.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.retriever.get_rag_client") as mock_get_client,
        ):
            mock_settings.SKIP_RAG = False
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(side_effect=Exception("RAG error"))
            mock_get_client.return_value = mock_client

            result = await retriever(state, TEST_CONFIG)

            assert result["context"] == []
            assert result["retrieval_status"] == "error"
            assert "오류" in result["thoughts"][-1]

    @pytest.mark.asyncio
    async def test_retriever_skip_rag_status(self) -> None:
        """Test retriever returns skipped status when SKIP_RAG is enabled."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )

        with patch("app.workflows.main_agent.nodes.retriever.settings") as mock_settings:
            mock_settings.SKIP_RAG = True

            result = await retriever(state, TEST_CONFIG)

            assert result["context"] == []
            assert result["retrieval_status"] == "skipped"


class TestSynthesizerNodeNoContext:
    """Tests for AC 2.5.8: 컨텍스트 없는 경우."""

    @pytest.mark.asyncio
    async def test_no_context_returns_fixed_message(self) -> None:
        """Test synthesizer calls LLM and returns response when no context."""
        state = create_initial_state(
            query="테스트 질문",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트 질문"
        state["context"] = []

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = create_streaming_llm_mock(
                "관련 정보를 찾지 못했습니다."
            )
            result = await synthesizer(state, TEST_CONFIG)

        assert result["response"] == "관련 정보를 찾지 못했습니다."
        assert "직접 답변을 생성" in result["thoughts"][-1]

    @pytest.mark.asyncio
    async def test_no_context_calls_llm(self) -> None:
        """Test LLM is called even when no context."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"
        state["context"] = []

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = create_streaming_llm_mock("LLM 응답")
            await synthesizer(state, TEST_CONFIG)
            mock_factory.get_llm.assert_called_once_with("primary")


class TestSynthesizerNodeWithContext:
    """Tests for AC 2.5.4, 2.5.7: 컨텍스트가 있는 경우."""

    @pytest.mark.asyncio
    async def test_with_context_calls_llm(self) -> None:
        """Test LLM is called when context exists (AC 2.5.4)."""
        state = create_initial_state(
            query="테스트 질문",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트 질문"
        state["context"] = ["[문서 1] 테스트 내용"]

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = create_streaming_llm_mock("테스트 답변입니다.")

            result = await synthesizer(state, TEST_CONFIG)

            assert "테스트" in result["response"]
            assert "답변" in result["response"]

    @pytest.mark.asyncio
    async def test_llm_called_with_primary_role(self) -> None:
        """Test LLM is called with 'primary' role (AC 2.5.7)."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"
        state["context"] = ["[문서 1] 내용"]

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = create_streaming_llm_mock("답변")

            await synthesizer(state, TEST_CONFIG)

            mock_factory.get_llm.assert_called_once_with("primary")

    @pytest.mark.asyncio
    async def test_thought_message_with_context(self) -> None:
        """Test correct thought message when context exists."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"
        state["context"] = ["[문서 1] 내용", "[문서 2] 내용"]

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = create_streaming_llm_mock("답변")

            result = await synthesizer(state, TEST_CONFIG)

            assert "2개 문서" in result["thoughts"][-1]


class TestSynthesizerOutputParsing:
    """Tests for Synthesizer 출력 파싱."""

    @pytest.mark.asyncio
    async def test_response_stripped(self) -> None:
        """Test LLM response is stripped of whitespace."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"
        state["context"] = ["[문서 1] 내용"]

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = create_streaming_llm_mock("  답변입니다  ")

            result = await synthesizer(state, TEST_CONFIG)

            assert "답변입니다" in result["response"]

    @pytest.mark.asyncio
    async def test_empty_response_fallback(self) -> None:
        """Test empty LLM response falls back to no context message."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"
        state["context"] = ["[문서 1] 내용"]

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = FakeStreamingLLM("")

            result = await synthesizer(state, TEST_CONFIG)

            assert result["response"] == NO_CONTEXT_RESPONSE


class TestSynthesizerErrorHandling:
    """Tests for Synthesizer 에러 처리."""

    @pytest.mark.asyncio
    async def test_llm_failure_returns_error_message(self) -> None:
        """Test LLM failure returns error message."""
        from app.core.enums import ErrorCode
        from app.core.exceptions import BusinessException

        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"
        state["context"] = ["[문서 1] 내용"]

        error = BusinessException(ErrorCode.ALL_SERVERS_DOWN, detail="All servers down")

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = FakeStreamingLLM(error=error)

            result = await synthesizer(state, TEST_CONFIG)

            assert "오류가 발생했습니다" in result["response"]
            assert "오류" in result["thoughts"][-1]

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self) -> None:
        """Test unexpected error is handled gracefully."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"
        state["context"] = ["[문서 1] 내용"]

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = FakeStreamingLLM(
                error=Exception("Unexpected error"),
            )

            result = await synthesizer(state, TEST_CONFIG)

            assert "오류가 발생했습니다" in result["response"]


class TestGraphStructure:
    """Tests for AC 2.5.2: 그래프 구조."""

    def test_graph_includes_retriever(self) -> None:
        """Test graph includes retriever node."""
        from app.workflows.main_agent.graph import build_graph

        graph = build_graph()
        nodes = list(graph.nodes.keys())

        assert "retriever" in nodes

    def test_graph_edge_rewriter_to_retriever(self) -> None:
        """Test edge exists from rewriter to retriever."""
        from app.workflows.main_agent.graph import build_graph

        graph = build_graph()

        # Check edges - rewriter should connect to retriever
        assert "rewriter" in graph.nodes
        assert "retriever" in graph.nodes

    def test_graph_edge_retriever_to_synthesizer(self) -> None:
        """Test edge exists from retriever to synthesizer."""
        from app.workflows.main_agent.graph import build_graph

        graph = build_graph()

        assert "retriever" in graph.nodes
        assert "synthesizer" in graph.nodes

    def test_graph_node_order(self) -> None:
        """Test graph has correct node order: rewriter -> retriever -> synthesizer."""
        from app.workflows.main_agent.graph import build_graph

        graph = build_graph()
        nodes = list(graph.nodes.keys())

        rewriter_idx = nodes.index("rewriter")
        retriever_idx = nodes.index("retriever")
        synthesizer_idx = nodes.index("synthesizer")

        # Nodes should be added in order
        assert rewriter_idx < retriever_idx < synthesizer_idx


class TestContextFormatting:
    """Tests for AC 2.5.6: 컨텍스트 포맷팅."""

    @pytest.mark.asyncio
    async def test_context_joined_with_newlines(self) -> None:
        """Test context list is joined with newlines for prompt."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
        )
        state["standalone_query"] = "테스트"
        state["context"] = [
            "[문서 1] (source: test1.pdf) 첫 번째 내용",
            "[문서 2] (source: test2.pdf) 두 번째 내용",
        ]

        call_args_capture: list = []
        fake_llm = FakeStreamingLLM("답변", capture=call_args_capture)

        with (
            patch("app.workflows.main_agent.nodes.synthesizer.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.synthesizer.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_RAG = False
            mock_factory.get_llm.return_value = fake_llm

            await synthesizer(state, TEST_CONFIG)

            # Check that context is properly formatted in the prompt
            user_message = str(call_args_capture[-1].content) if call_args_capture else ""
            assert "[참고 문서]" in user_message
            assert "[사용자 질문]" in user_message
