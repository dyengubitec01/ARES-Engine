"""
LangFuse Prompt Management 통합 테스트 (Story 3.4).

실제 LangFuse 서버에 연결하여 프롬프트 fetch/fallback 동작을 검증한다.
LangFuse가 설정되어 있지 않으면 자동 스킵.

실행: uv run pytest tests/integration/test_prompt_management.py -v -m integration
"""

import pytest

from tests.integration.conftest import skip_no_langfuse


@pytest.mark.integration
class TestLangFusePromptFetch:
    """실제 LangFuse 서버에서 프롬프트를 가져오는 통합 테스트."""

    @skip_no_langfuse
    def test_fetch_rewriter_prompt(self) -> None:
        """rewriter 프롬프트를 LangFuse에서 정상 fetch."""
        from app.core.prompt_manager import PromptConfig, PromptManager

        config = PromptConfig()
        manager = PromptManager(config=config)

        prompt = manager.get_prompt(
            "rewriter",
            fallback_messages=[("system", "fallback"), ("user", "{query}")],
        )

        assert prompt is not None
        assert "history" in prompt.input_variables
        assert "query" in prompt.input_variables

    @skip_no_langfuse
    def test_fetch_synthesizer_prompt(self) -> None:
        """synthesizer 프롬프트를 LangFuse에서 정상 fetch."""
        from app.core.prompt_manager import PromptConfig, PromptManager

        config = PromptConfig()
        manager = PromptManager(config=config)

        prompt = manager.get_prompt(
            "synthesizer",
            fallback_messages=[("system", "fallback"), ("user", "{query}")],
        )

        assert prompt is not None
        assert "context" in prompt.input_variables
        assert "query" in prompt.input_variables

    @skip_no_langfuse
    def test_fetch_router_prompt(self) -> None:
        """router 프롬프트를 LangFuse에서 정상 fetch."""
        from app.core.prompt_manager import PromptConfig, PromptManager

        config = PromptConfig()
        manager = PromptManager(config=config)

        prompt = manager.get_prompt(
            "router",
            fallback_messages=[
                ("system", "fallback {routes_text} {route_options}"),
                ("user", "{query}"),
            ],
        )

        assert prompt is not None

    @skip_no_langfuse
    def test_prefetch_all(self) -> None:
        """모든 프롬프트 pre-fetch 정상 동작."""
        from app.core.prompt_manager import PromptConfig, PromptManager

        config = PromptConfig()
        manager = PromptManager(config=config)

        # 예외 없이 완료되어야 함
        manager.prefetch_all()


@pytest.mark.integration
class TestLangFusePromptFallback:
    """LangFuse 불가 시 fallback 동작 통합 테스트."""

    def test_fallback_when_langfuse_disabled(self) -> None:
        """LangFuse 비활성화 시 하드코딩 fallback 사용."""
        from unittest.mock import patch

        from app.core.prompt_manager import PromptConfig, PromptManager

        config = PromptConfig()
        manager = PromptManager(config=config)

        hardcoded = [
            ("system", "Hardcoded rewriter {history}"),
            ("user", "{query}"),
        ]

        with patch("app.core.prompt_manager.settings") as mock_settings:
            mock_settings.langfuse_prompt_enabled = False

            prompt = manager.get_prompt("rewriter", fallback_messages=hardcoded)

        assert prompt is not None
        assert "history" in prompt.input_variables
        assert "query" in prompt.input_variables

    def test_fallback_with_wrong_key(self) -> None:
        """잘못된 API 키 → LangFuse fetch 실패 → fallback 사용."""
        import os
        from unittest.mock import patch

        from app.core.prompt_manager import PromptConfig, PromptManager

        config = PromptConfig()
        manager = PromptManager(config=config)

        hardcoded = [
            ("system", "Hardcoded rewriter {history}"),
            ("user", "{query}"),
        ]

        # 잘못된 키로 LangFuse 클라이언트 생성
        with patch.dict(os.environ, {
            "LANGFUSE_PUBLIC_KEY": "pk-wrong-key",
            "LANGFUSE_SECRET_KEY": "sk-wrong-key",
            "LANGFUSE_HOST": "http://localhost:3100",
        }):
            with patch("app.core.prompt_manager.settings") as mock_settings:
                mock_settings.langfuse_prompt_enabled = True
                mock_settings.LANGFUSE_PROMPT_CACHE_TTL = 0

                # 새 클라이언트 강제 생성
                manager._langfuse_client = None

                prompt = manager.get_prompt(
                    "rewriter", fallback_messages=hardcoded
                )

        assert prompt is not None
        assert "history" in prompt.input_variables


@pytest.mark.integration
class TestPromptNodeIntegration:
    """노드에서 프롬프트를 가져오는 통합 테스트."""

    @skip_no_langfuse
    def test_rewriter_node_uses_langfuse_prompt(self) -> None:
        """rewriter 노드가 LangFuse 프롬프트를 정상적으로 사용."""
        from app.workflows.main_agent.prompts.rewriter import (
            get_rewriter_prompt,
        )

        prompt = get_rewriter_prompt()
        assert prompt is not None

        # format_messages가 정상 동작하는지
        messages = prompt.format_messages(
            history="<user>안녕</user>\n<assistant>안녕하세요</assistant>",
            query="그거 알려줘",
        )
        assert len(messages) >= 2

    @skip_no_langfuse
    def test_synthesizer_node_uses_langfuse_prompt(self) -> None:
        """synthesizer 노드가 LangFuse 프롬프트를 정상적으로 사용."""
        from app.workflows.main_agent.prompts.synthesizer import (
            get_synthesizer_prompt,
        )

        prompt = get_synthesizer_prompt()
        assert prompt is not None

        messages = prompt.format_messages(
            history="(이전 대화 없음)",
            context="[문서1] 연차휴가는 15일입니다.",
            query="휴가 규정 알려줘",
        )
        assert len(messages) >= 2

    @skip_no_langfuse
    def test_router_build_with_langfuse(self) -> None:
        """router가 LangFuse 프롬프트 + 동적 변수 주입 정상 동작."""
        from app.workflows.main_agent.prompts.router import (
            build_router_prompt,
        )

        prompt = build_router_prompt(["rag", "direct"])
        assert prompt is not None

        # query만 남아있어야 함 (routes_text, route_options는 partial로 주입됨)
        messages = prompt.format_messages(query="사내 휴가 규정 알려줘")
        assert len(messages) >= 2
        # system 메시지에 경로 설명이 포함되어야 함
        system_content = messages[0].content
        assert "rag" in system_content
        assert "direct" in system_content
