"""Tests for RAG Client - Story 2.3."""

import pytest

from app.clients.rag_client import (
    Document,
    MockRAGClient,
    RAGClient,
    RAGClientProtocol,
    format_documents_for_context,
    get_rag_client,
)
from app.core.enums import ErrorCode
from app.core.exceptions import BusinessException


class TestDocument:
    """Tests for Document model (AC 2.3.1)."""

    def test_document_creation(self) -> None:
        """Test creating a Document with all required fields."""
        doc = Document(
            content="Test content",
            metadata={"source": "test.pdf", "page": 1},
            score=0.95,
        )
        assert doc.content == "Test content"
        assert doc.metadata == {"source": "test.pdf", "page": 1}
        assert doc.score == 0.95

    def test_document_with_empty_metadata(self) -> None:
        """Test creating a Document with empty metadata."""
        doc = Document(content="Content", metadata={}, score=0.5)
        assert doc.metadata == {}

    def test_document_score_range(self) -> None:
        """Test document with various score values."""
        doc_high = Document(content="High", metadata={}, score=1.0)
        doc_low = Document(content="Low", metadata={}, score=0.0)
        assert doc_high.score == 1.0
        assert doc_low.score == 0.0


class TestMockRAGClient:
    """Tests for MockRAGClient (AC 2.3.2)."""

    @pytest.fixture
    def mock_client(self) -> MockRAGClient:
        """Create a MockRAGClient instance."""
        return MockRAGClient()

    @pytest.mark.asyncio
    async def test_search_returns_documents(self, mock_client: MockRAGClient) -> None:
        """Test that search returns a list of Document instances."""
        results = await mock_client.search("test query")
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(doc, Document) for doc in results)

    @pytest.mark.asyncio
    async def test_search_returns_all_documents(self, mock_client: MockRAGClient) -> None:
        """Test search returns all sample documents (no top_k truncation)."""
        results = await mock_client.search("test query")
        assert len(results) == len(mock_client._sample_documents)

    @pytest.mark.asyncio
    async def test_search_documents_have_valid_structure(
        self, mock_client: MockRAGClient
    ) -> None:
        """Test that returned documents have valid structure."""
        results = await mock_client.search("query")
        for doc in results:
            assert isinstance(doc.content, str)
            assert len(doc.content) > 0
            assert isinstance(doc.metadata, dict)
            assert isinstance(doc.score, float)
            assert 0.0 <= doc.score <= 1.0

    @pytest.mark.asyncio
    async def test_search_returns_sorted_by_score(
        self, mock_client: MockRAGClient
    ) -> None:
        """Test that results are sorted by score in descending order."""
        results = await mock_client.search("query")
        scores = [doc.score for doc in results]
        assert scores == sorted(scores, reverse=True)

    def test_mock_client_implements_protocol(self) -> None:
        """Test that MockRAGClient implements RAGClientProtocol."""
        client = MockRAGClient()
        assert isinstance(client, RAGClientProtocol)


class TestRAGClient:
    """Tests for RAGClient (AC 2.3.3)."""

    def test_rag_client_creation_with_defaults(self) -> None:
        """Test creating RAGClient with default settings."""
        client = RAGClient()
        assert client.base_url is not None
        assert client.timeout > 0

    def test_rag_client_creation_with_custom_params(self) -> None:
        """Test creating RAGClient with custom parameters."""
        client = RAGClient(base_url="http://custom:8000", timeout=30.0)
        assert client.base_url == "http://custom:8000"
        assert client.timeout == 30.0

    @pytest.mark.asyncio
    async def test_rag_client_search_connection_error(self) -> None:
        """Test that RAGClient.search raises BusinessException on connection failure."""
        client = RAGClient(base_url="http://localhost:19999", timeout=1.0)
        with pytest.raises(BusinessException) as exc_info:
            await client.search("test query")
        assert exc_info.value.error_code == ErrorCode.RAG_SEARCH

    def test_rag_client_implements_protocol(self) -> None:
        """Test that RAGClient implements RAGClientProtocol."""
        client = RAGClient()
        assert isinstance(client, RAGClientProtocol)

    @pytest.mark.asyncio
    async def test_rag_client_context_manager(self) -> None:
        """Test that RAGClient supports async context manager."""
        async with RAGClient() as client:
            assert client is not None
            assert isinstance(client, RAGClient)
        # close()가 자동 호출되어 _client가 None이어야 함
        assert client._client is None


class TestGetRAGClient:
    """Tests for get_rag_client factory function (AC 2.3.4)."""

    def test_get_mock_rag_client_when_use_mock_true(self) -> None:
        """Test factory returns MockRAGClient when USE_MOCK_RAG=True."""
        from unittest.mock import patch

        with patch("app.clients.rag_client.get_settings") as mock_settings:
            mock_settings.return_value.USE_MOCK_RAG = True
            mock_settings.return_value.RAG_BASE_URL = "http://localhost:8001"
            mock_settings.return_value.RAG_TIMEOUT = 10.0

            client = get_rag_client()
            assert isinstance(client, MockRAGClient)

    def test_get_real_rag_client_when_use_mock_false(self) -> None:
        """Test factory returns RAGClient when USE_MOCK_RAG=False."""
        from unittest.mock import patch

        with patch("app.clients.rag_client.get_settings") as mock_settings:
            mock_settings.return_value.USE_MOCK_RAG = False
            mock_settings.return_value.RAG_BASE_URL = "http://rag-server:8001"
            mock_settings.return_value.RAG_TIMEOUT = 15.0

            client = get_rag_client()
            assert isinstance(client, RAGClient)
            assert client.base_url == "http://rag-server:8001"
            assert client.timeout == 15.0


class TestRAGClientSearchBody:
    """RAG 검색 body 구성 테스트 (AC 3.6.1, 3.6.3, 3.6.4)."""

    @staticmethod
    def _make_mock_client() -> RAGClient:
        from unittest.mock import AsyncMock, MagicMock

        client = RAGClient(base_url="http://localhost:8001", timeout=1.0)
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": {"results": []}}
        mock_response.raise_for_status.return_value = None
        mock_http.post = AsyncMock(return_value=mock_response)
        client._client = mock_http
        return client

    @pytest.mark.asyncio
    async def test_search_body_includes_user_depts_array(self) -> None:
        """user_depts 배열이 body에 포함 (AC 3.6.1)."""
        client = self._make_mock_client()
        await client.search("test", user_depts=["D001", "D002"])

        body = client._client.post.call_args.kwargs["json"]
        assert body["user_depts"] == ["D001", "D002"]

    @pytest.mark.asyncio
    async def test_search_body_includes_excluded_docs(self) -> None:
        """excluded_docs가 body에 포함 (AC 3.6.3)."""
        client = self._make_mock_client()
        await client.search("test", excluded_docs=["cid-1", "cid-2"])

        body = client._client.post.call_args.kwargs["json"]
        assert body["excluded_docs"] == ["cid-1", "cid-2"]

    @pytest.mark.asyncio
    async def test_search_body_excludes_empty_excluded_docs(self) -> None:
        """빈 excluded_docs는 body에서 제외 (AC 3.6.4)."""
        client = self._make_mock_client()
        await client.search("test", excluded_docs=[])

        body = client._client.post.call_args.kwargs["json"]
        assert "excluded_docs" not in body

    @pytest.mark.asyncio
    async def test_search_body_excludes_none_excluded_docs(self) -> None:
        """None excluded_docs는 body에서 제외 (AC 3.6.4)."""
        client = self._make_mock_client()
        await client.search("test")

        body = client._client.post.call_args.kwargs["json"]
        assert "excluded_docs" not in body


class TestFormatDocumentsForContext:
    """Tests for format_documents_for_context function (AC 2.3.5)."""

    def test_format_single_document(self) -> None:
        """Test formatting a single document with XML tags."""
        docs = [Document(content="Test content", metadata={}, score=0.9)]
        result = format_documents_for_context(docs)
        assert len(result) == 1
        assert result[0] == "<document>\nTest content\n</document>"

    def test_format_multiple_documents(self) -> None:
        """Test formatting multiple documents with XML tags."""
        docs = [
            Document(content="First", metadata={}, score=0.9),
            Document(content="Second", metadata={}, score=0.8),
            Document(content="Third", metadata={}, score=0.7),
        ]
        result = format_documents_for_context(docs)
        assert len(result) == 3
        for r in result:
            assert r.startswith("<document>\n")
            assert r.endswith("\n</document>")
        assert "First" in result[0]
        assert "Second" in result[1]
        assert "Third" in result[2]

    def test_format_empty_documents(self) -> None:
        """Test formatting empty document list."""
        result = format_documents_for_context([])
        assert result == []

    def test_format_preserves_content(self) -> None:
        """Test that formatting preserves document content."""
        content = "This is important information about the topic."
        docs = [Document(content=content, metadata={}, score=0.95)]
        result = format_documents_for_context(docs)
        assert content in result[0]

    def test_format_excludes_metadata(self) -> None:
        """Test that formatting excludes metadata from context."""
        docs = [
            Document(
                content="Content",
                metadata={"source": "document.pdf"},
                score=0.9,
            )
        ]
        result = format_documents_for_context(docs)
        assert result[0] == "<document>\nContent\n</document>"
        assert "document.pdf" not in result[0]
