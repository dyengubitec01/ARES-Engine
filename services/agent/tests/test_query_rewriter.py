"""Tests for Story 2.2: Query Rewriter 노드 구현."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.workflows.main_agent import create_initial_state
from app.workflows.main_agent.nodes.rewriter import (
    format_history_for_prompt,
    rewriter,
)
from app.workflows.main_agent.prompts.rewriter import REWRITER_PROMPT


class TestRewriterPrompt:
    """Tests for AC 2.2.2: Rewriter 프롬프트."""

    def test_prompt_is_chat_prompt_template(self) -> None:
        """Test REWRITER_PROMPT is a ChatPromptTemplate."""
        from langchain_core.prompts import ChatPromptTemplate

        assert isinstance(REWRITER_PROMPT, ChatPromptTemplate)

    def test_prompt_has_required_variables(self) -> None:
        """Test prompt template has history and query variables."""
        input_vars = REWRITER_PROMPT.input_variables
        assert "history" in input_vars
        assert "query" in input_vars

    def test_prompt_format_produces_messages(self) -> None:
        """Test prompt can be formatted into messages."""
        messages = REWRITER_PROMPT.format_messages(
            history="사용자: 갤럭시 S24에 대해 알려줘",
            query="그거 얼마야?",
        )

        assert len(messages) >= 2  # system + user at minimum
        assert any("재구성" in str(m.content) for m in messages)


class TestHistoryFormatting:
    """Tests for History Formatting 함수."""

    def test_format_empty_history(self) -> None:
        """Test formatting empty history returns placeholder."""
        result = format_history_for_prompt([])
        assert result == "(이전 대화 없음)"

    def test_format_single_turn_history(self) -> None:
        """Test formatting single turn history."""
        history = [{"role": "user", "content": "갤럭시 S24에 대해 알려줘"}]
        result = format_history_for_prompt(history)

        assert "<user>" in result
        assert "갤럭시 S24" in result

    def test_format_multi_turn_history(self) -> None:
        """Test formatting multi-turn history."""
        history = [
            {"role": "user", "content": "갤럭시 S24에 대해 알려줘"},
            {"role": "assistant", "content": "갤럭시 S24는 삼성의 플래그십 스마트폰입니다."},
            {"role": "user", "content": "배터리 용량은?"},
        ]
        result = format_history_for_prompt(history)

        assert "<user>" in result
        assert "<assistant>" in result
        assert result.count("\n") >= 2  # Multiple lines

    def test_format_assistant_role_as_xml_tag(self) -> None:
        """Test assistant role is formatted as XML tag."""
        history = [{"role": "assistant", "content": "테스트 응답"}]
        result = format_history_for_prompt(history)

        assert "<assistant>테스트 응답</assistant>" in result

    def test_ai_prefix_not_accumulated_across_turns(self) -> None:
        """대화 이력에 'AI: ' 포함된 content가 있어도 포맷에 '\\nAI: ' 패턴이 없다."""
        history = [
            {"role": "user", "content": "질문"},
            {"role": "assistant", "content": "AI: 이전 응답"},
            {"role": "user", "content": "다음 질문"},
        ]
        result = format_history_for_prompt(history)

        assert "\nAI: " not in result

    def test_no_ai_prefix_pattern_in_format(self) -> None:
        """포맷 결과에 'AI:' 또는 '사용자:' 접두사 패턴이 없다."""
        history = [
            {"role": "user", "content": "안녕"},
            {"role": "assistant", "content": "안녕하세요"},
        ]
        result = format_history_for_prompt(history)

        assert "AI:" not in result
        assert "사용자:" not in result


class TestRewriterNodeNoHistory:
    """Tests for AC 2.2.3: 이력 없는 경우."""

    @pytest.mark.asyncio
    async def test_no_history_returns_original_query(self) -> None:
        """Test rewriter returns original query when no history."""
        state = create_initial_state(
            query="안녕하세요",
            session_id="test-123",
            history=[],
        )

        result = await rewriter(state)

        assert result["standalone_query"] == "안녕하세요"

    @pytest.mark.asyncio
    async def test_no_history_no_llm_call(self) -> None:
        """Test LLM is not called when no history."""
        state = create_initial_state(
            query="테스트 질문",
            session_id="test-123",
            history=[],
        )

        with patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory:
            await rewriter(state)
            mock_factory.invoke_chain_with_failover.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_history_thought_message(self) -> None:
        """Test correct thought message when no history (AC 2.2.7)."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
            history=[],
        )

        with patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings:
            mock_settings.SKIP_REWRITER = False
            result = await rewriter(state)

        assert "대화 이력이 없어 원본 질문을 그대로 사용합니다." in result["thoughts"]


class TestRewriterNodeWithHistory:
    """Tests for AC 2.2.1, 2.2.4: 이력이 있는 경우 LLM 호출."""

    @pytest.mark.asyncio
    async def test_with_history_calls_llm(self) -> None:
        """Test LLM is called when history exists."""
        state = create_initial_state(
            query="그거 얼마야?",
            session_id="test-123",
            history=[{"role": "user", "content": "갤럭시 S24에 대해 알려줘"}],
        )

        mock_response = AIMessage(content="갤럭시 S24의 가격은 얼마인가요?")

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)

            result = await rewriter(state)

            mock_factory.invoke_chain_with_failover.assert_called_once()
            assert result["standalone_query"] == "갤럭시 S24의 가격은 얼마인가요?"

    @pytest.mark.asyncio
    async def test_llm_called_with_primary_role(self) -> None:
        """Test LLM is called with 'primary' role (AC 2.2.4)."""
        state = create_initial_state(
            query="그거 얼마야?",
            session_id="test-123",
            history=[{"role": "user", "content": "갤럭시 S24"}],
        )

        mock_response = AIMessage(content="재구성된 질문")

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)

            await rewriter(state)

            call_kwargs = mock_factory.invoke_chain_with_failover.call_args
            assert call_kwargs.kwargs.get("role") == "primary"

    @pytest.mark.asyncio
    async def test_llm_called_with_session_id(self) -> None:
        """Test LLM is called with session_id for tracing (AC 2.2.4)."""
        state = create_initial_state(
            query="질문",
            session_id="trace-session-456",
            history=[{"role": "user", "content": "이전 대화"}],
        )

        mock_response = AIMessage(content="재구성된 질문")

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)

            await rewriter(state)

            call_kwargs = mock_factory.invoke_chain_with_failover.call_args
            assert call_kwargs.kwargs.get("session_id") == "trace-session-456"

    @pytest.mark.asyncio
    async def test_llm_called_with_request_type(self) -> None:
        """Test LLM is called with request_type='query_rewrite' (AC 2.2.4)."""
        state = create_initial_state(
            query="질문",
            session_id="test-123",
            history=[{"role": "user", "content": "이전 대화"}],
        )

        mock_response = AIMessage(content="재구성된 질문")

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)

            await rewriter(state)

            call_kwargs = mock_factory.invoke_chain_with_failover.call_args
            assert call_kwargs.kwargs.get("request_type") == "query_rewrite"

    @pytest.mark.asyncio
    async def test_with_history_thought_message(self) -> None:
        """Test correct thought message when history exists (AC 2.2.7)."""
        state = create_initial_state(
            query="질문",
            session_id="test-123",
            history=[{"role": "user", "content": "이전 대화"}],
        )

        mock_response = AIMessage(content="재구성된 질문")

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)

            result = await rewriter(state)

            assert "대화 맥락을 반영하여 질문을 명확히 했습니다." in result["thoughts"]


class TestOutputParsing:
    """Tests for AC 2.2.6: 출력 파싱."""

    @pytest.mark.asyncio
    async def test_empty_response_fallback_to_original(self) -> None:
        """Test empty LLM response falls back to original query."""
        state = create_initial_state(
            query="원본 질문",
            session_id="test-123",
            history=[{"role": "user", "content": "이전 대화"}],
        )

        mock_response = AIMessage(content="")

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)

            result = await rewriter(state)

            assert result["standalone_query"] == "원본 질문"

    @pytest.mark.asyncio
    async def test_whitespace_response_fallback_to_original(self) -> None:
        """Test whitespace-only LLM response falls back to original query."""
        state = create_initial_state(
            query="원본 질문",
            session_id="test-123",
            history=[{"role": "user", "content": "이전 대화"}],
        )

        mock_response = AIMessage(content="   \n\t  ")

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)

            result = await rewriter(state)

            assert result["standalone_query"] == "원본 질문"

    @pytest.mark.asyncio
    async def test_none_content_fallback_to_original(self) -> None:
        """Test None content falls back to original query."""
        state = create_initial_state(
            query="원본 질문",
            session_id="test-123",
            history=[{"role": "user", "content": "이전 대화"}],
        )

        mock_response = MagicMock()
        mock_response.content = None

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)

            result = await rewriter(state)

            assert result["standalone_query"] == "원본 질문"

    @pytest.mark.asyncio
    async def test_response_stripped(self) -> None:
        """Test LLM response is stripped of whitespace."""
        state = create_initial_state(
            query="질문",
            session_id="test-123",
            history=[{"role": "user", "content": "이전"}],
        )

        mock_response = AIMessage(content="  재구성된 질문  \n")

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_chain_with_failover = AsyncMock(return_value=mock_response)

            result = await rewriter(state)

            assert result["standalone_query"] == "재구성된 질문"


class TestFailoverBehavior:
    """Tests for Failover 동작."""

    @pytest.mark.asyncio
    async def test_llm_failure_fallback_to_original(self) -> None:
        """Test LLM failure falls back to original query (AC 2.2.4)."""
        from app.core.enums import ErrorCode
        from app.core.exceptions import BusinessException

        state = create_initial_state(
            query="원본 질문",
            session_id="test-123",
            history=[{"role": "user", "content": "이전 대화"}],
        )

        with (
            patch("app.workflows.main_agent.nodes.rewriter.settings") as mock_settings,
            patch("app.workflows.main_agent.nodes.rewriter.llm_factory") as mock_factory,
        ):
            mock_settings.SKIP_REWRITER = False
            mock_factory.invoke_chain_with_failover = AsyncMock(
                side_effect=BusinessException(ErrorCode.ALL_SERVERS_DOWN, detail="All servers down")
            )

            result = await rewriter(state)

            assert result["standalone_query"] == "원본 질문"
            assert result.get("error") is None  # 워크플로우는 계속 진행


class TestStateUpdate:
    """Tests for AC 2.2.5: 상태 업데이트."""

    @pytest.mark.asyncio
    async def test_returns_only_required_fields(self) -> None:
        """Test rewriter returns only standalone_query and thoughts."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
            history=[],
        )

        result = await rewriter(state)

        assert set(result.keys()) == {"standalone_query", "thoughts"}

    @pytest.mark.asyncio
    async def test_thoughts_returns_own_only(self) -> None:
        """Test node returns only its own thought (reducer handles merging)."""
        state = create_initial_state(
            query="테스트",
            session_id="test-123",
            history=[],
        )
        state["thoughts"] = ["기존 생각"]

        result = await rewriter(state)

        # Story 2.8: reducer 패턴 - 노드는 자기 thought만 반환
        assert len(result["thoughts"]) == 1
        assert isinstance(result["thoughts"][0], str)


class TestRewriterPromptGuidelines:
    """Tests for Rewriter 프롬프트 가이드라인 (프롬프트 재작성 후)."""

    def test_prompt_has_semantic_preservation(self) -> None:
        """프롬프트에 의미 보존 가이드라인이 포함되어 있다."""
        system_msg = REWRITER_PROMPT.format_messages(history="", query="")[0].content
        assert "의미 보존" in system_msg

    def test_prompt_has_minimal_edit_principle(self) -> None:
        """프롬프트에 최소 수정 원칙이 포함되어 있다."""
        system_msg = REWRITER_PROMPT.format_messages(history="", query="")[0].content
        assert "최소 수정" in system_msg

    def test_prompt_has_no_keyword_addition_rule(self) -> None:
        """프롬프트에 단어 추가 금지 규칙이 포함되어 있다."""
        system_msg = REWRITER_PROMPT.format_messages(history="", query="")[0].content
        assert "단어 추가 금지" in system_msg

    def test_prompt_has_new_topic_isolation(self) -> None:
        """프롬프트에 새 주제 격리 규칙이 포함되어 있다."""
        system_msg = REWRITER_PROMPT.format_messages(history="", query="")[0].content
        assert "새 주제" in system_msg or "새로운 주제" in system_msg

    def test_prompt_has_at_least_three_guidelines(self) -> None:
        """프롬프트에 최소 3개의 가이드라인이 있다."""
        system_msg = REWRITER_PROMPT.format_messages(history="", query="")[0].content
        # 가이드라인 번호 매기기 패턴 (1., 2., 3., 4.)
        guideline_count = sum(1 for i in range(1, 10) if f"{i}." in system_msg)
        assert guideline_count >= 3


class TestShortQueries:
    """Tests for 짧은 query 처리."""

    @pytest.mark.asyncio
    async def test_single_char_query(self) -> None:
        """Test single character query is handled."""
        state = create_initial_state(
            query="야",
            session_id="test-123",
            history=[],
        )

        result = await rewriter(state)

        assert result["standalone_query"] == "야"

    @pytest.mark.asyncio
    async def test_short_greeting_query(self) -> None:
        """Test short greeting query is handled."""
        state = create_initial_state(
            query="응",
            session_id="test-123",
            history=[],
        )

        result = await rewriter(state)

        assert result["standalone_query"] == "응"

    @pytest.mark.asyncio
    async def test_hello_query(self) -> None:
        """Test '안녕' query is handled."""
        state = create_initial_state(
            query="안녕",
            session_id="test-123",
            history=[],
        )

        result = await rewriter(state)

        assert result["standalone_query"] == "안녕"
