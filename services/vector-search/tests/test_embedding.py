"""임베딩 어댑터 테스트."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.adapters.embedding_adapter import EmbeddingAdapter
from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
from app.core.config import Settings
from app.core.exceptions import EmbeddingException
from app.core.interfaces import EmbeddingInterface


class TestMockEmbeddingAdapter:
    """MockEmbeddingAdapter 테스트."""

    async def test_implements_interface(self):
        """EmbeddingInterface를 구현한다."""
        adapter = MockEmbeddingAdapter()
        assert isinstance(adapter, EmbeddingInterface)

    async def test_returns_list_of_floats(self):
        """list[float] 타입의 벡터를 반환한다."""
        adapter = MockEmbeddingAdapter()
        result = await adapter.embed("테스트 쿼리")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    async def test_returns_1024_dimension(self):
        """1024 차원의 벡터를 반환한다."""
        adapter = MockEmbeddingAdapter()
        result = await adapter.embed("테스트 쿼리")
        assert len(result) == 1024

    async def test_returns_consistent_dimension(self):
        """다른 입력에 대해서도 동일한 차원을 반환한다."""
        adapter = MockEmbeddingAdapter()
        result_a = await adapter.embed("첫 번째 쿼리")
        result_b = await adapter.embed("두 번째 쿼리")
        assert len(result_a) == len(result_b)


class TestEmbeddingAdapter:
    """EmbeddingAdapter 테스트."""

    def _make_settings(self, **overrides) -> Settings:
        """테스트용 Settings 인스턴스를 생성한다."""
        defaults = {
            "EMBEDDING_API_URL": "http://test-server:8100/query",
            "HTTP_TIMEOUT": 5.0,
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def _make_mock_client(self, *, post_return=None, post_side_effect=None):
        """httpx.AsyncClient mock을 생성한다."""
        mock_client = AsyncMock()
        if post_side_effect is not None:
            mock_client.post.side_effect = post_side_effect
        elif post_return is not None:
            mock_client.post.return_value = post_return
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return mock_client

    def _make_response(self, *, status_code=200, json_data=None, url=None):
        """httpx.Response mock을 생성한다."""
        request = httpx.Request("POST", url or "http://test-server:8100/query")
        return httpx.Response(
            status_code=status_code,
            json=json_data,
            request=request,
        )

    async def test_implements_interface(self):
        """EmbeddingInterface를 구현한다."""
        settings = self._make_settings()
        adapter = EmbeddingAdapter(settings)
        assert isinstance(adapter, EmbeddingInterface)

    async def test_successful_embedding(self):
        """성공 시 API 응답에서 벡터를 추출하여 반환한다."""
        settings = self._make_settings()
        adapter = EmbeddingAdapter(settings)
        expected_vector = [0.1, 0.2, 0.3]

        response = self._make_response(json_data={
            "query": "테스트", "model": "bge-m3", "dim": 3,
            "vector": expected_vector,
        })

        with patch("app.adapters.embedding_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            result = await adapter.embed("테스트")

        assert result == expected_vector

    async def test_sends_correct_request_body(self):
        """요청 본문에 query 필드를 포함하여 전송한다."""
        settings = self._make_settings()
        adapter = EmbeddingAdapter(settings)

        response = self._make_response(json_data={
            "query": "안녕하세요", "model": "bge-m3", "dim": 1, "vector": [0.1],
        })

        with patch("app.adapters.embedding_adapter.httpx.AsyncClient") as cls:
            mock_client = self._make_mock_client(post_return=response)
            cls.return_value = mock_client
            await adapter.embed("안녕하세요")

        mock_client.post.assert_called_once_with(
            settings.EMBEDDING_API_URL,
            json={"query": "안녕하세요"},
        )

    async def test_uses_configured_timeout(self):
        """Settings.HTTP_TIMEOUT 값이 httpx 클라이언트에 적용된다."""
        settings = self._make_settings(HTTP_TIMEOUT=10.0)
        adapter = EmbeddingAdapter(settings)

        response = self._make_response(json_data={
            "query": "q", "model": "bge-m3", "dim": 1, "vector": [0.1],
        })

        with patch("app.adapters.embedding_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            await adapter.embed("q")

        cls.assert_called_once_with(timeout=10.0)

    async def test_timeout_raises_embedding_exception(self):
        """타임아웃 발생 시 EmbeddingException을 raise한다."""
        settings = self._make_settings()
        adapter = EmbeddingAdapter(settings)

        with patch("app.adapters.embedding_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(
                post_side_effect=httpx.TimeoutException("timeout"),
            )
            with pytest.raises(EmbeddingException, match="타임아웃"):
                await adapter.embed("테스트")

    async def test_connect_error_raises_embedding_exception(self):
        """연결 실패 시 EmbeddingException을 raise한다."""
        settings = self._make_settings()
        adapter = EmbeddingAdapter(settings)

        with patch("app.adapters.embedding_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(
                post_side_effect=httpx.ConnectError("connection refused"),
            )
            with pytest.raises(EmbeddingException, match="연결 실패"):
                await adapter.embed("테스트")

    async def test_http_status_error_raises_embedding_exception(self):
        """HTTP 에러 응답 시 EmbeddingException을 raise한다."""
        settings = self._make_settings()
        adapter = EmbeddingAdapter(settings)

        response = self._make_response(status_code=500)

        with patch("app.adapters.embedding_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            with pytest.raises(EmbeddingException, match="HTTP 에러"):
                await adapter.embed("테스트")

    async def test_exception_has_correct_rag_code(self):
        """EmbeddingException의 RAG 코드가 RAG100040이다."""
        settings = self._make_settings()
        adapter = EmbeddingAdapter(settings)

        with patch("app.adapters.embedding_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(
                post_side_effect=httpx.ConnectError("refused"),
            )
            with pytest.raises(EmbeddingException) as exc_info:
                await adapter.embed("테스트")

        assert exc_info.value.code.value == "RAG100040"
        assert exc_info.value.status_code == 502

    async def test_missing_vector_key_raises_embedding_exception(self):
        """응답에 vector 키가 없으면 EmbeddingException을 raise한다."""
        settings = self._make_settings()
        adapter = EmbeddingAdapter(settings)

        response = self._make_response(json_data={
            "query": "테스트", "model": "bge-m3", "dim": 1024,
        })

        with patch("app.adapters.embedding_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            with pytest.raises(EmbeddingException, match="파싱 실패"):
                await adapter.embed("테스트")

    async def test_invalid_json_raises_embedding_exception(self):
        """응답이 유효한 JSON이 아니면 EmbeddingException을 raise한다."""
        settings = self._make_settings()
        adapter = EmbeddingAdapter(settings)

        request = httpx.Request("POST", settings.EMBEDDING_API_URL)
        raw_response = httpx.Response(
            status_code=200,
            content=b"not json",
            request=request,
        )

        with patch("app.adapters.embedding_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=raw_response)
            with pytest.raises(EmbeddingException, match="파싱 실패"):
                await adapter.embed("테스트")
