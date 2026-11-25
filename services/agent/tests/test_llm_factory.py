"""Tests for LLM Factory."""

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.core.config import ModelConfig, RoleConfig, ServerConfig
from app.core.enums import ErrorCode
from app.core.exceptions import BusinessException
from app.core.llm_factory import LLMFactory


class TestLLMFactory:
    """Tests for LLMFactory class."""

    @pytest.fixture
    def sample_config(self) -> ModelConfig:
        """Create sample model config for testing."""
        return ModelConfig(
            roles={
                "primary": RoleConfig(
                    model="primary-model",
                    server="primary",
                    fallback_role="fallback",
                ),
                "fallback": RoleConfig(
                    model="fallback-model",
                    server="secondary",
                    fallback_role=None,
                ),
                "fast": RoleConfig(
                    model="fast-model",
                    server="primary",
                    fallback_role="primary",
                ),
            },
            servers={
                "primary": ServerConfig(base_url_env="PRIMARY_LLM_BASE_URL"),
                "secondary": ServerConfig(base_url_env="SECONDARY_LLM_BASE_URL"),
            },
            fallback_message="Service unavailable",
        )

    @pytest.fixture
    def factory(self, sample_config: ModelConfig) -> LLMFactory:
        """Create factory with sample config."""
        return LLMFactory(config=sample_config)

    def test_get_model_for_role(self, factory: LLMFactory) -> None:
        """Test getting model name for a role."""
        assert factory.get_model_for_role("primary") == "primary-model"
        assert factory.get_model_for_role("fallback") == "fallback-model"
        assert factory.get_model_for_role("fast") == "fast-model"

    def test_get_model_for_unknown_role(self, factory: LLMFactory) -> None:
        """Test getting model for unknown role returns None."""
        assert factory.get_model_for_role("unknown") is None

    def test_get_fallback_role(self, factory: LLMFactory) -> None:
        """Test getting fallback role."""
        assert factory.get_fallback_role("primary") == "fallback"
        assert factory.get_fallback_role("fast") == "primary"
        assert factory.get_fallback_role("fallback") is None

    def test_fallback_message(self, factory: LLMFactory) -> None:
        """Test fallback message."""
        assert factory.fallback_message == "Service unavailable"

    def test_get_base_url(self, factory: LLMFactory, monkeypatch) -> None:
        """Test getting base URL for role."""
        monkeypatch.setenv("PRIMARY_LLM_BASE_URL", "http://localhost:11434/v1")
        # settings 캐시를 우회하기 위해 직접 패치
        from app.core.config import Settings
        monkeypatch.setattr("app.core.config.settings", Settings())

        url = factory.get_base_url("primary")
        assert url is not None
        assert "localhost" in url

    def test_get_model_with_fallback_direct(self, factory: LLMFactory) -> None:
        """Test get_model_with_fallback returns direct match."""
        result = factory.get_model_with_fallback("primary")

        assert result is not None
        model, url = result
        assert model == "primary-model"
        assert url is not None

    def test_get_model_with_fallback_chain(self, factory: LLMFactory) -> None:
        """Test fallback chain is followed."""
        # fast -> primary -> fallback
        result = factory.get_model_with_fallback("fast")

        assert result is not None
        model, _ = result
        assert model == "fast-model"

    def test_get_model_with_fallback_unknown(self, factory: LLMFactory) -> None:
        """Test unknown role returns None."""
        result = factory.get_model_with_fallback("unknown")

        assert result is None


class TestLLMFactoryLangChain:
    """Tests for LLMFactory LangChain integration (Story 1.3)."""

    @pytest.fixture
    def sample_config(self) -> ModelConfig:
        """Create sample model config for testing."""
        return ModelConfig(
            roles={
                "primary": RoleConfig(
                    model="primary-model",
                    server="primary",
                    fallback_role="fallback",
                ),
                "fallback": RoleConfig(
                    model="fallback-model",
                    server="secondary",
                    fallback_role=None,
                ),
                "fast": RoleConfig(
                    model="fast-model",
                    server="primary",
                    fallback_role="primary",
                ),
            },
            servers={
                "primary": ServerConfig(base_url_env="PRIMARY_LLM_BASE_URL"),
                "secondary": ServerConfig(base_url_env="SECONDARY_LLM_BASE_URL"),
            },
            fallback_message="Service unavailable",
        )

    @pytest.fixture
    def factory(self, sample_config: ModelConfig) -> LLMFactory:
        """Create factory with sample config."""
        return LLMFactory(config=sample_config)

    def test_get_llm_returns_chat_openai(self, factory: LLMFactory) -> None:
        """Test get_llm returns ChatOpenAI instance."""
        llm = factory.get_llm("primary")

        assert isinstance(llm, ChatOpenAI)
        assert llm.model_name == "primary-model"

    def test_get_llm_includes_max_tokens(self, factory: LLMFactory, monkeypatch) -> None:
        """Test get_llm passes max_tokens from settings."""
        from app.core.config import Settings
        monkeypatch.setattr("app.core.config.settings", Settings(_env_file=None))
        factory._llm_cache.clear()
        llm = factory.get_llm("primary")

        assert llm.max_tokens == 2048

    def test_get_llm_includes_temperature(self, factory: LLMFactory, monkeypatch) -> None:
        """Test get_llm passes temperature from settings."""
        from app.core.config import Settings
        monkeypatch.setattr("app.core.config.settings", Settings(_env_file=None))
        factory._llm_cache.clear()
        llm = factory.get_llm("primary")

        assert llm.temperature == 0.6

    def test_get_llm_caching_same_role(self, factory: LLMFactory) -> None:
        """Test get_llm returns cached instance for same role."""
        llm1 = factory.get_llm("primary")
        llm2 = factory.get_llm("primary")

        assert llm1 is llm2

    def test_get_llm_different_roles_different_instances(
        self, factory: LLMFactory
    ) -> None:
        """Test get_llm returns different instances for different roles."""
        llm_primary = factory.get_llm("primary")
        llm_fast = factory.get_llm("fast")

        assert llm_primary is not llm_fast
        assert llm_primary.model_name == "primary-model"
        assert llm_fast.model_name == "fast-model"

    def test_get_llm_unknown_role_raises_error(self, factory: LLMFactory) -> None:
        """Test get_llm raises ValueError for unknown role."""
        with pytest.raises(ValueError) as exc_info:
            factory.get_llm("unknown_role")

        error_msg = str(exc_info.value)
        assert "unknown_role" in error_msg
        assert "primary" in error_msg  # Available roles should be listed

    def test_get_llm_api_key_not_needed(self, factory: LLMFactory, monkeypatch) -> None:
        """Test get_llm sets api_key to 'not-needed' for on-premise."""
        monkeypatch.setenv("LLM_API_KEY", "not-needed")
        from app.core.config import Settings
        monkeypatch.setattr("app.core.config.settings", Settings())
        factory._llm_cache.clear()

        llm = factory.get_llm("primary")

        assert llm.openai_api_key.get_secret_value() == "not-needed"

    def test_get_available_roles(self, factory: LLMFactory) -> None:
        """Test _get_available_roles returns all role names."""
        roles = factory._get_available_roles()

        assert "primary" in roles
        assert "fallback" in roles
        assert "fast" in roles
        assert len(roles) == 3


class TestLLMFactoryAsync:
    """Async tests for LLMFactory invoke and stream methods."""

    @pytest.fixture
    def sample_config(self) -> ModelConfig:
        """Create sample model config for testing."""
        return ModelConfig(
            roles={
                "primary": RoleConfig(
                    model="primary-model",
                    server="primary",
                    fallback_role="fallback",
                ),
                "fallback": RoleConfig(
                    model="fallback-model",
                    server="secondary",
                    fallback_role=None,
                ),
            },
            servers={
                "primary": ServerConfig(base_url_env="PRIMARY_LLM_BASE_URL"),
                "secondary": ServerConfig(base_url_env="SECONDARY_LLM_BASE_URL"),
            },
            fallback_message="Service unavailable",
        )

    @pytest.fixture
    def factory(self, sample_config: ModelConfig) -> LLMFactory:
        """Create factory with sample config."""
        return LLMFactory(config=sample_config)

    @pytest.mark.asyncio
    async def test_invoke_returns_ai_message(self, factory: LLMFactory) -> None:
        """Test invoke returns AIMessage (mocked)."""
        mock_response = AIMessage(content="Hello from LLM")

        with patch.object(ChatOpenAI, "ainvoke", new_callable=AsyncMock) as mock_ainvoke:
            mock_ainvoke.return_value = mock_response

            result = await factory.invoke("primary", [HumanMessage(content="test")])

            assert isinstance(result, AIMessage)
            assert result.content == "Hello from LLM"
            mock_ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self, factory: LLMFactory) -> None:
        """Test stream yields AIMessageChunks (mocked)."""
        mock_chunks = [
            AIMessageChunk(content="Hello"),
            AIMessageChunk(content=" from"),
            AIMessageChunk(content=" LLM"),
        ]

        async def mock_astream(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk

        with patch.object(ChatOpenAI, "astream", mock_astream):
            chunks = []
            async for chunk in factory.stream("primary", [HumanMessage(content="test")]):
                chunks.append(chunk)

            assert len(chunks) == 3
            assert all(isinstance(c, AIMessageChunk) for c in chunks)
            assert "".join(c.content for c in chunks) == "Hello from LLM"

    @pytest.mark.asyncio
    async def test_invoke_unknown_role_raises_error(self, factory: LLMFactory) -> None:
        """Test invoke raises ValueError for unknown role."""
        with pytest.raises(ValueError) as exc_info:
            await factory.invoke("unknown", [HumanMessage(content="test")])

        assert "unknown" in str(exc_info.value)


class TestLLMFactoryFailover:
    """Tests for LLMFactory failover mechanism (Story 1.4)."""

    @pytest.fixture
    def sample_config(self) -> ModelConfig:
        """Create sample model config for testing."""
        return ModelConfig(
            roles={
                "primary": RoleConfig(
                    model="primary-model",
                    server="primary",
                    fallback_role="fallback",
                ),
                "fallback": RoleConfig(
                    model="fallback-model",
                    server="secondary",
                    fallback_role=None,
                ),
                "fast": RoleConfig(
                    model="fast-model",
                    server="primary",
                    fallback_role="primary",
                ),
            },
            servers={
                "primary": ServerConfig(base_url_env="PRIMARY_LLM_BASE_URL"),
                "secondary": ServerConfig(base_url_env="SECONDARY_LLM_BASE_URL"),
            },
            fallback_message="Service unavailable",
        )

    @pytest.fixture
    def factory(self, sample_config: ModelConfig) -> LLMFactory:
        """Create factory with sample config."""
        return LLMFactory(config=sample_config)

    @pytest.mark.asyncio
    async def test_invoke_with_failover_success(self, factory: LLMFactory) -> None:
        """Test invoke_with_failover returns response on success."""
        mock_response = AIMessage(content="Hello from LLM")

        with patch.object(ChatOpenAI, "ainvoke", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await factory.invoke_with_failover(
                "primary", [HumanMessage(content="test")]
            )

            assert isinstance(result, AIMessage)
            assert result.content == "Hello from LLM"

    @pytest.mark.asyncio
    async def test_invoke_with_failover_on_connect_error(
        self, factory: LLMFactory
    ) -> None:
        """Test failover triggers on ConnectError."""
        call_count = 0

        async def mock_ainvoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # primary 호출 (1회 + 1회 재시도)
                raise httpx.ConnectError("Connection refused")
            return AIMessage(content="Fallback response")

        with patch.object(ChatOpenAI, "ainvoke", side_effect=mock_ainvoke):
            result = await factory.invoke_with_failover(
                "primary", [HumanMessage(content="test")]
            )

            assert result.content == "Fallback response"
            assert call_count == 3  # primary 2회 + fallback 1회

    @pytest.mark.asyncio
    async def test_invoke_with_failover_on_timeout(self, factory: LLMFactory) -> None:
        """Test failover triggers on TimeoutException."""
        call_count = 0

        async def mock_ainvoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # primary 호출 (1회 + 1회 재시도)
                raise httpx.TimeoutException("Request timeout")
            return AIMessage(content="Fallback response")

        with patch.object(ChatOpenAI, "ainvoke", side_effect=mock_ainvoke):
            result = await factory.invoke_with_failover(
                "primary", [HumanMessage(content="test")]
            )

            assert result.content == "Fallback response"
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_invoke_with_failover_graceful_degradation(
        self, factory: LLMFactory
    ) -> None:
        """Test graceful degradation when all servers fail."""
        with patch.object(
            ChatOpenAI,
            "ainvoke",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("All servers down"),
        ):
            with pytest.raises(BusinessException) as exc_info:
                await factory.invoke_with_failover(
                    "primary", [HumanMessage(content="test")]
                )

            assert exc_info.value.error_code == ErrorCode.ALL_SERVERS_DOWN
            assert exc_info.value.code == "AGT5010"

    @pytest.mark.asyncio
    async def test_invoke_with_failover_retry_before_failover(
        self, factory: LLMFactory
    ) -> None:
        """Test retry logic: 1 retry before failover."""
        call_count = 0

        async def mock_ainvoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # 첫 번째 호출만 실패
                raise httpx.ConnectError("Connection refused")
            return AIMessage(content="Success after retry")

        with patch.object(ChatOpenAI, "ainvoke", side_effect=mock_ainvoke):
            result = await factory.invoke_with_failover(
                "primary", [HumanMessage(content="test")]
            )

            assert result.content == "Success after retry"
            assert call_count == 2  # 재시도 성공, fallback 안 감

    @pytest.mark.asyncio
    async def test_invoke_with_failover_logging(
        self,
        factory: LLMFactory,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test failover logs warning message."""
        call_count = 0

        async def mock_ainvoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise httpx.ConnectError("Connection refused")
            return AIMessage(content="Fallback response")

        with caplog.at_level(logging.WARNING):
            with patch.object(ChatOpenAI, "ainvoke", side_effect=mock_ainvoke):
                await factory.invoke_with_failover(
                    "primary", [HumanMessage(content="test")]
                )

        # structlog 설정 상태에 따라 stdout 또는 caplog에 기록됨
        stdout_output = capsys.readouterr().out
        caplog_output = " ".join(str(getattr(r, "msg", "")) for r in caplog.records)
        assert "llm_failover_triggered" in stdout_output or "llm_failover_triggered" in caplog_output

    @pytest.mark.asyncio
    async def test_stream_with_failover_success(self, factory: LLMFactory) -> None:
        """Test stream_with_failover yields chunks on success."""
        mock_chunks = [
            AIMessageChunk(content="Hello"),
            AIMessageChunk(content=" World"),
        ]

        async def mock_astream(*args, **kwargs):
            for chunk in mock_chunks:
                yield chunk

        with patch.object(ChatOpenAI, "astream", mock_astream):
            chunks = []
            async for chunk in factory.stream_with_failover(
                "primary", [HumanMessage(content="test")]
            ):
                chunks.append(chunk)

            assert len(chunks) == 2
            assert "".join(c.content for c in chunks) == "Hello World"

    @pytest.mark.asyncio
    async def test_stream_with_failover_on_error(self, factory: LLMFactory) -> None:
        """Test stream_with_failover triggers failover on error."""
        call_count = 0
        mock_chunks = [
            AIMessageChunk(content="Fallback"),
            AIMessageChunk(content=" response"),
        ]

        async def mock_astream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # primary 2회 실패
                raise httpx.ConnectError("Connection refused")
            for chunk in mock_chunks:
                yield chunk

        with patch.object(ChatOpenAI, "astream", mock_astream):
            chunks = []
            async for chunk in factory.stream_with_failover(
                "primary", [HumanMessage(content="test")]
            ):
                chunks.append(chunk)

            assert "".join(c.content for c in chunks) == "Fallback response"
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_stream_with_failover_graceful_degradation(
        self, factory: LLMFactory
    ) -> None:
        """Test stream graceful degradation when all servers fail."""

        async def mock_astream(*args, **kwargs):
            raise httpx.ConnectError("All servers down")
            yield  # Make it a generator

        with patch.object(ChatOpenAI, "astream", mock_astream):
            with pytest.raises(BusinessException) as exc_info:
                async for _ in factory.stream_with_failover(
                    "primary", [HumanMessage(content="test")]
                ):
                    pass

            assert exc_info.value.error_code == ErrorCode.ALL_SERVERS_DOWN
            assert exc_info.value.code == "AGT5010"

    @pytest.mark.asyncio
    async def test_invoke_with_failover_unknown_role(self, factory: LLMFactory) -> None:
        """Test invoke_with_failover raises ValueError for unknown role."""
        with pytest.raises(ValueError) as exc_info:
            await factory.invoke_with_failover(
                "unknown", [HumanMessage(content="test")]
            )

        assert "unknown" in str(exc_info.value)


class TestLLMFactoryChainFailover:
    """Tests for invoke_chain_with_failover (Story 3.8)."""

    @pytest.fixture
    def sample_config(self) -> ModelConfig:
        return ModelConfig(
            roles={
                "primary": RoleConfig(
                    model="primary-model",
                    server="primary",
                    fallback_role="fallback",
                ),
                "fallback": RoleConfig(
                    model="fallback-model",
                    server="secondary",
                    fallback_role=None,
                ),
            },
            servers={
                "primary": ServerConfig(base_url_env="PRIMARY_LLM_BASE_URL"),
                "secondary": ServerConfig(base_url_env="SECONDARY_LLM_BASE_URL"),
            },
            fallback_message="Service unavailable",
        )

    @pytest.fixture
    def factory(self, sample_config: ModelConfig) -> LLMFactory:
        return LLMFactory(config=sample_config)

    @pytest.fixture
    def simple_prompt(self) -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant."),
            ("user", "{query}"),
        ])

    @pytest.mark.asyncio
    async def test_chain_invoke_success(
        self, factory: LLMFactory, simple_prompt: ChatPromptTemplate
    ) -> None:
        """chain 패턴으로 정상 호출 시 AIMessage를 반환한다."""
        mock_response = AIMessage(content="Chain response")

        with patch.object(ChatOpenAI, "ainvoke", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await factory.invoke_chain_with_failover(
                "primary", simple_prompt, {"query": "test"}
            )

            assert isinstance(result, AIMessage)
            assert result.content == "Chain response"

    @pytest.mark.asyncio
    async def test_chain_failover_on_connect_error(
        self, factory: LLMFactory, simple_prompt: ChatPromptTemplate
    ) -> None:
        """primary 실패 시 fallback으로 전환된다."""
        call_count = 0

        async def mock_ainvoke(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise httpx.ConnectError("Connection refused")
            return AIMessage(content="Fallback response")

        with patch.object(ChatOpenAI, "ainvoke", side_effect=mock_ainvoke):
            result = await factory.invoke_chain_with_failover(
                "primary", simple_prompt, {"query": "test"}
            )

            assert result.content == "Fallback response"
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_chain_graceful_degradation(
        self, factory: LLMFactory, simple_prompt: ChatPromptTemplate
    ) -> None:
        """모든 서버 실패 시 ALL_SERVERS_DOWN 예외를 발생시킨다."""
        with patch.object(
            ChatOpenAI,
            "ainvoke",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("All servers down"),
        ):
            with pytest.raises(BusinessException) as exc_info:
                await factory.invoke_chain_with_failover(
                    "primary", simple_prompt, {"query": "test"}
                )

            assert exc_info.value.error_code == ErrorCode.ALL_SERVERS_DOWN

    @pytest.mark.asyncio
    async def test_chain_passes_trace_metadata_to_tracing_config(
        self, factory: LLMFactory, simple_prompt: ChatPromptTemplate
    ) -> None:
        """trace_metadata가 _prepare_tracing_config에 올바르게 전달된다."""
        mock_response = AIMessage(content="ok")

        with (
            patch.object(
                ChatOpenAI, "ainvoke", new_callable=AsyncMock, return_value=mock_response,
            ),
            patch.object(
                factory, "_prepare_tracing_config", wraps=factory._prepare_tracing_config,
            ) as mock_prep,
        ):
            await factory.invoke_chain_with_failover(
                "primary",
                simple_prompt,
                {"query": "test"},
                session_id="sess-1",
                request_type="query_rewrite",
                trace_metadata={"original_query": "원본 질문"},
            )

            mock_prep.assert_called_once_with(
                session_id="sess-1",
                user_id=None,
                request_type="query_rewrite",
                trace_metadata={"original_query": "원본 질문"},
            )
