"""Tests for Prompt-Generation 연결 (AC 3.8.1~3.8.5).

chain 패턴(prompt | llm) 전환 후:
- PromptTemplate.metadata의 langfuse_prompt가 chain을 통해 자동 전파되는지 검증
- partial()이 metadata를 보존하는지 검증
"""

from unittest.mock import MagicMock

from langchain_core.prompts import ChatPromptTemplate

SIMPLE_ROUTER_MESSAGES = [
    ("system", "Route: {routes_text}\nOptions: {route_options}"),
    ("user", "{query}"),
]


# ============================================================================
# ChatPromptTemplate.partial() 메타데이터 보존 검증
# ============================================================================

class TestPartialPreservesMetadata:
    """partial()이 langfuse_prompt metadata를 보존하는지 검증.

    Router는 prompt_manager.get_prompt() → .partial(routes_text=..., route_options=...)
    순서로 프롬프트를 생성하므로, partial()이 metadata를 유실하면 연결이 끊어진다.
    """

    def test_partial_preserves_langfuse_prompt_metadata(self) -> None:
        """partial() 호출 후에도 langfuse_prompt metadata가 유지된다."""
        sentinel = MagicMock(name="langfuse_prompt_sentinel")
        template = ChatPromptTemplate.from_messages(SIMPLE_ROUTER_MESSAGES)
        template.metadata = {"langfuse_prompt": sentinel}

        partial_template = template.partial(
            routes_text="- rag\n- tool",
            route_options="rag, tool",
        )

        assert partial_template.metadata is not None
        assert partial_template.metadata.get("langfuse_prompt") is sentinel

    def test_partial_without_metadata_returns_none(self) -> None:
        """metadata가 없는 템플릿에 partial()을 해도 에러 없이 동작한다."""
        template = ChatPromptTemplate.from_messages(SIMPLE_ROUTER_MESSAGES)

        partial_template = template.partial(
            routes_text="- rag",
            route_options="rag",
        )

        lf_prompt = (partial_template.metadata or {}).get("langfuse_prompt")
        assert lf_prompt is None
