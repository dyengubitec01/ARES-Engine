"""Qdrant 벡터 검색 어댑터 테스트."""

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import QueryResponse, ScoredPoint

from app.adapters.qdrant_adapter import QdrantAdapter
from app.core.config import Settings
from app.core.exceptions import VectorStoreException
from app.core.interfaces import VectorStoreInterface
from app.core.payload_fields import PayloadField


class TestQdrantAdapter:
    """QdrantAdapter 테스트."""

    def _make_settings(self, **overrides) -> Settings:
        """테스트용 Settings 인스턴스를 생성한다."""
        defaults = {
            "QDRANT_URL": "http://test-qdrant:6333",
            "QDRANT_COLLECTION": "test-collection",
            "QDRANT_CONTENT_FIELD": "text_for_search",
        }
        defaults.update(overrides)
        return Settings(**defaults)

    def _make_adapter(
        self,
        settings: Settings | None = None,
        mock_client: AsyncMock | None = None,
    ) -> tuple[QdrantAdapter, AsyncMock]:
        """테스트용 QdrantAdapter와 mock client를 생성한다."""
        s = settings or self._make_settings()
        client = mock_client or AsyncMock(spec=AsyncQdrantClient)
        with patch(
            "app.adapters.qdrant_adapter.AsyncQdrantClient",
            return_value=client,
        ):
            adapter = QdrantAdapter(settings=s)
        return adapter, client

    def _make_query_response(
        self, points: list[ScoredPoint] | None = None
    ) -> QueryResponse:
        """QueryResponse mock을 생성한다."""
        return QueryResponse(points=points or [])

    def _make_scored_point(
        self,
        *,
        point_id: int = 1,
        score: float = 0.95,
        payload: dict | None = None,
    ) -> ScoredPoint:
        """ScoredPoint mock을 생성한다."""
        return ScoredPoint(
            id=point_id,
            version=1,
            score=score,
            payload=payload or {"text_for_search": "테스트 문서", "doc_content_id": "test-001"},
        )

    async def test_implements_interface(self):
        """VectorStoreInterface를 구현한다."""
        adapter, _ = self._make_adapter()
        assert isinstance(adapter, VectorStoreInterface)

    async def test_uses_settings_for_connection(self):
        """Settings의 QDRANT_URL로 AsyncQdrantClient를 생성한다."""
        settings = self._make_settings(QDRANT_URL="http://custom:6333")
        with patch(
            "app.adapters.qdrant_adapter.AsyncQdrantClient",
        ) as mock_cls:
            mock_cls.return_value = AsyncMock(spec=AsyncQdrantClient)
            QdrantAdapter(settings=settings)

        mock_cls.assert_called_once_with(url="http://custom:6333")

    async def test_uses_settings_collection_name(self):
        """Settings의 QDRANT_COLLECTION을 사용한다."""
        settings = self._make_settings(QDRANT_COLLECTION="my-docs")
        adapter, client = self._make_adapter(settings=settings)
        client.query_points.return_value = self._make_query_response()

        await adapter.search(query_vector=[0.1], top_k=5, user_depts=["test-dept"])

        call_kwargs = client.query_points.call_args.kwargs
        assert call_kwargs["collection_name"] == "my-docs"
        assert call_kwargs["query"] == [0.1]
        assert call_kwargs["limit"] == 5

    async def test_dept_filter_not_applied(self):
        """부서 필터 개방: user_depts를 받아도 query_filter에 auth_dept_id 조건이 포함되지 않는다."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        adapter, client = self._make_adapter()
        client.query_points.return_value = self._make_query_response()

        await adapter.search(query_vector=[0.1], top_k=5, user_depts=["dept-uuid-123", "dept-uuid-456"])

        call_kwargs = client.query_points.call_args.kwargs
        query_filter = call_kwargs["query_filter"]
        must_keys = [c.key for c in query_filter.must]
        assert PayloadField.AUTH_DEPT_ID not in must_keys
        expected_filter = Filter(
            must=[
                FieldCondition(
                    key=PayloadField.IS_ACTIVE,
                    match=MatchValue(value="Y"),
                ),
            ]
        )
        assert query_filter == expected_filter

    async def test_excluded_docs_filter(self):
        """excluded_docs 전달 시 must_not 조건으로 DOC_CONTENT_ID를 제외한다."""
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        adapter, client = self._make_adapter()
        client.query_points.return_value = self._make_query_response()

        await adapter.search(
            query_vector=[0.1], top_k=5,
            user_depts=["dept-uuid-123"],
            excluded_docs=["dc-0001", "dc-0042"],
        )

        call_kwargs = client.query_points.call_args.kwargs
        expected_filter = Filter(
            must=[
                FieldCondition(
                    key=PayloadField.IS_ACTIVE,
                    match=MatchValue(value="Y"),
                ),
            ],
            must_not=[
                FieldCondition(
                    key=PayloadField.DOC_CONTENT_ID,
                    match=MatchAny(any=["dc-0001", "dc-0042"]),
                )
            ],
        )
        assert call_kwargs["query_filter"] == expected_filter

    async def test_query_filter_includes_is_active(self):
        """query_filter의 must 조건에 is_active = 'Y' FieldCondition이 포함된다."""
        from qdrant_client.models import FieldCondition, MatchValue

        adapter, client = self._make_adapter()
        client.query_points.return_value = self._make_query_response()

        await adapter.search(query_vector=[0.1], top_k=5, user_depts=["dept-uuid-123"])

        call_kwargs = client.query_points.call_args.kwargs
        query_filter = call_kwargs["query_filter"]
        is_active_condition = FieldCondition(
            key=PayloadField.IS_ACTIVE,
            match=MatchValue(value="Y"),
        )
        assert is_active_condition in query_filter.must

    async def test_empty_excluded_docs_no_must_not(self):
        """excluded_docs가 빈 리스트이면 must_not 조건이 없다."""
        adapter, client = self._make_adapter()
        client.query_points.return_value = self._make_query_response()

        await adapter.search(
            query_vector=[0.1], top_k=5,
            user_depts=["dept-uuid-123"],
            excluded_docs=[],
        )

        call_kwargs = client.query_points.call_args.kwargs
        query_filter = call_kwargs["query_filter"]
        assert len(query_filter.must) == 1
        assert query_filter.must_not is None

    async def test_successful_search(self):
        """성공 시 content, metadata, score를 포함하는 결과를 반환한다."""
        adapter, client = self._make_adapter()
        client.query_points.return_value = self._make_query_response(
            points=[
                self._make_scored_point(
                    point_id=1,
                    score=0.95,
                    payload={"text_for_search": "문서 A", "doc_content_id": "doc-a", "original_filename": "a.pdf"},
                ),
                self._make_scored_point(
                    point_id=2,
                    score=0.80,
                    payload={"text_for_search": "문서 B", "doc_content_id": "doc-b", "original_filename": "b.pdf"},
                ),
            ]
        )

        results = await adapter.search(query_vector=[0.1, 0.2], top_k=5, user_depts=["test-dept"])

        assert len(results) == 2
        assert results[0]["content"] == "문서 A"
        assert results[0]["metadata"] == {"doc_content_id": "doc-a", "original_filename": "a.pdf"}
        assert results[0]["score"] == 0.95
        assert results[1]["content"] == "문서 B"
        assert results[1]["metadata"] == {"doc_content_id": "doc-b", "original_filename": "b.pdf"}
        assert results[1]["score"] == 0.80

    async def test_empty_results_returns_empty_list(self):
        """검색 결과가 없으면 빈 리스트를 반환한다."""
        adapter, client = self._make_adapter()
        client.query_points.return_value = self._make_query_response(points=[])

        results = await adapter.search(query_vector=[0.1], top_k=5, user_depts=["test-dept"])

        assert results == []

    async def test_content_field_extraction(self):
        """text_for_search 필드를 content로 추출하고 나머지는 metadata로 분리한다."""
        adapter, client = self._make_adapter()
        client.query_points.return_value = self._make_query_response(
            points=[
                self._make_scored_point(
                    payload={
                        "text_for_search": "본문 텍스트",
                        "doc_content_id": "doc-001",
                        "original_filename": "doc.pdf",
                        "page_start": 5,
                    }
                ),
            ]
        )

        results = await adapter.search(query_vector=[0.1], top_k=1, user_depts=["test-dept"])

        assert results[0]["content"] == "본문 텍스트"
        assert results[0]["metadata"] == {
            "doc_content_id": "doc-001",
            "original_filename": "doc.pdf",
            "page_start": 5,
        }

    async def test_custom_content_field(self):
        """QDRANT_CONTENT_FIELD 설정으로 다른 필드명을 사용할 수 있다."""
        settings = self._make_settings(QDRANT_CONTENT_FIELD="body")
        adapter, client = self._make_adapter(settings=settings)
        client.query_points.return_value = self._make_query_response(
            points=[
                self._make_scored_point(
                    payload={"body": "커스텀 본문", "doc_content_id": "doc-001"},
                ),
            ]
        )

        results = await adapter.search(query_vector=[0.1], top_k=1, user_depts=["test-dept"])

        assert results[0]["content"] == "커스텀 본문"
        assert "body" not in results[0]["metadata"]
        assert results[0]["metadata"] == {"doc_content_id": "doc-001"}

    async def test_missing_content_field_returns_empty_string(self):
        """payload에 text_for_search 필드가 없으면 빈 문자열을 반환한다."""
        adapter, client = self._make_adapter()
        client.query_points.return_value = self._make_query_response(
            points=[
                self._make_scored_point(
                    payload={"doc_content_id": "doc-001", "original_filename": "doc.pdf"},
                ),
            ]
        )

        results = await adapter.search(query_vector=[0.1], top_k=1, user_depts=["test-dept"])

        assert results[0]["content"] == ""
        assert results[0]["metadata"] == {"doc_content_id": "doc-001", "original_filename": "doc.pdf"}

    async def test_unexpected_response_raises_vector_store_exception(self):
        """UnexpectedResponse 발생 시 VectorStoreException을 raise한다."""
        adapter, client = self._make_adapter()
        client.query_points.side_effect = UnexpectedResponse(
            status_code=500,
            reason_phrase="Internal Server Error",
            content=b"error",
            headers=httpx.Headers(),
        )

        with pytest.raises(VectorStoreException, match="검색 에러"):
            await adapter.search(query_vector=[0.1], top_k=5, user_depts=["test-dept"])

    async def test_connect_error_raises_vector_store_exception(self):
        """연결 실패 시 VectorStoreException을 raise한다."""
        adapter, client = self._make_adapter()
        client.query_points.side_effect = httpx.ConnectError("connection refused")

        with pytest.raises(VectorStoreException, match="연결 실패"):
            await adapter.search(query_vector=[0.1], top_k=5, user_depts=["test-dept"])

    async def test_timeout_raises_vector_store_exception(self):
        """타임아웃 발생 시 VectorStoreException을 raise한다."""
        adapter, client = self._make_adapter()
        client.query_points.side_effect = httpx.TimeoutException("timeout")

        with pytest.raises(VectorStoreException, match="타임아웃"):
            await adapter.search(query_vector=[0.1], top_k=5, user_depts=["test-dept"])

    async def test_exception_has_correct_rag_code(self):
        """VectorStoreException의 RAG 코드가 RAG100060이다."""
        adapter, client = self._make_adapter()
        client.query_points.side_effect = httpx.ConnectError("refused")

        with pytest.raises(VectorStoreException) as exc_info:
            await adapter.search(query_vector=[0.1], top_k=5, user_depts=["test-dept"])

        assert exc_info.value.code.value == "RAG100060"
        assert exc_info.value.status_code == 502

    async def test_parse_error_raises_vector_store_exception(self):
        """응답 파싱 실패 시 VectorStoreException을 raise한다."""
        adapter, client = self._make_adapter()
        bad_point = self._make_scored_point(payload={"text_for_search": "ok"})
        bad_point.payload = None  # type: ignore[assignment]
        client.query_points.return_value = self._make_query_response(
            points=[bad_point]
        )

        with pytest.raises(VectorStoreException, match="파싱 실패"):
            await adapter.search(query_vector=[0.1], top_k=1, user_depts=["test-dept"])

    async def test_connect_error_logs_message(self, caplog):
        """연결 실패 시 에러 로그가 기록된다."""
        adapter, client = self._make_adapter()
        client.query_points.side_effect = httpx.ConnectError("refused")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(VectorStoreException):
                await adapter.search(query_vector=[0.1], top_k=5, user_depts=["test-dept"])

        assert "Qdrant 연결 실패" in caplog.text
        assert "test-collection" in caplog.text

    async def test_timeout_logs_message(self, caplog):
        """타임아웃 발생 시 에러 로그가 기록된다."""
        adapter, client = self._make_adapter()
        client.query_points.side_effect = httpx.TimeoutException("timeout")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(VectorStoreException):
                await adapter.search(query_vector=[0.1], top_k=5, user_depts=["test-dept"])

        assert "Qdrant 요청 타임아웃" in caplog.text

    async def test_search_returns_point_id(self):
        """search 반환 dict에 _point_id(Qdrant point.id)가 포함된다."""
        adapter, client = self._make_adapter()
        client.query_points.return_value = self._make_query_response(
            points=[
                self._make_scored_point(
                    point_id=42,
                    payload={"text_for_search": "문서", "doc_content_id": "dc-001"},
                ),
            ]
        )

        results = await adapter.search(
            query_vector=[0.1], top_k=1, user_depts=["test-dept"]
        )

        assert results[0]["_point_id"] == 42


class TestQdrantAdapterTextSearch:
    """QdrantAdapter.text_search (BM25) 테스트."""

    def _make_adapter(self) -> tuple[QdrantAdapter, AsyncMock]:
        client = AsyncMock(spec=AsyncQdrantClient)
        settings = Settings(
            QDRANT_URL="http://test-qdrant:6333",
            QDRANT_COLLECTION="test-collection",
            QDRANT_CONTENT_FIELD="text_for_search",
        )
        with patch(
            "app.adapters.qdrant_adapter.AsyncQdrantClient", return_value=client
        ):
            adapter = QdrantAdapter(settings=settings)
        return adapter, client

    def _make_point(
        self, *, point_id: int = 1, score: float = 5.0, payload: dict | None = None
    ) -> ScoredPoint:
        return ScoredPoint(
            id=point_id,
            version=1,
            score=score,
            payload=payload or {"text_for_search": "문서", "doc_content_id": "dc-001"},
        )

    async def test_uses_match_text_filter(self):
        """text_search는 content_field에 MatchText 조건을 건다."""
        from qdrant_client.models import FieldCondition, MatchText

        adapter, client = self._make_adapter()
        client.query_points.return_value = QueryResponse(points=[])

        await adapter.text_search(
            query_text="연차 사용 규정",
            top_k=5,
            user_depts=["dept-1"],
        )

        call_kwargs = client.query_points.call_args.kwargs
        assert call_kwargs["collection_name"] == "test-collection"
        assert call_kwargs["limit"] == 5
        assert "query" not in call_kwargs
        query_filter = call_kwargs["query_filter"]
        text_condition = FieldCondition(
            key="text_for_search", match=MatchText(text="연차 사용 규정")
        )
        assert text_condition in query_filter.must

    async def test_reuses_common_filter(self):
        """text_search는 is_active, excluded_docs 공유 필터를 재사용하며 부서 필터는 적용하지 않는다."""
        from qdrant_client.models import FieldCondition, MatchAny, MatchValue

        adapter, client = self._make_adapter()
        client.query_points.return_value = QueryResponse(points=[])

        await adapter.text_search(
            query_text="query",
            top_k=3,
            user_depts=["dept-1", "dept-2"],
            excluded_docs=["dc-0001"],
        )

        query_filter = client.query_points.call_args.kwargs["query_filter"]
        assert PayloadField.AUTH_DEPT_ID not in [c.key for c in query_filter.must]
        assert FieldCondition(
            key=PayloadField.IS_ACTIVE, match=MatchValue(value="Y")
        ) in query_filter.must
        assert query_filter.must_not == [
            FieldCondition(
                key=PayloadField.DOC_CONTENT_ID,
                match=MatchAny(any=["dc-0001"]),
            )
        ]

    async def test_returns_point_id_and_content(self):
        """text_search 반환 dict에도 _point_id가 포함된다."""
        adapter, client = self._make_adapter()
        client.query_points.return_value = QueryResponse(
            points=[
                self._make_point(
                    point_id=77,
                    score=12.3,
                    payload={
                        "text_for_search": "BM25 히트",
                        "doc_content_id": "dc-077",
                    },
                )
            ]
        )

        results = await adapter.text_search(
            query_text="히트", top_k=1, user_depts=["d"]
        )

        assert len(results) == 1
        assert results[0]["_point_id"] == 77
        assert results[0]["content"] == "BM25 히트"
        assert results[0]["metadata"] == {"doc_content_id": "dc-077"}
        assert results[0]["score"] == 12.3

    async def test_empty_results(self):
        adapter, client = self._make_adapter()
        client.query_points.return_value = QueryResponse(points=[])

        results = await adapter.text_search(
            query_text="nothing", top_k=5, user_depts=["d"]
        )

        assert results == []

    async def test_connect_error_raises(self):
        adapter, client = self._make_adapter()
        client.query_points.side_effect = httpx.ConnectError("refused")

        with pytest.raises(VectorStoreException, match="BM25"):
            await adapter.text_search(
                query_text="q", top_k=5, user_depts=["d"]
            )

    async def test_timeout_raises(self):
        adapter, client = self._make_adapter()
        client.query_points.side_effect = httpx.TimeoutException("timeout")

        with pytest.raises(VectorStoreException, match="BM25"):
            await adapter.text_search(
                query_text="q", top_k=5, user_depts=["d"]
            )

    async def test_unexpected_response_raises(self):
        adapter, client = self._make_adapter()
        client.query_points.side_effect = UnexpectedResponse(
            status_code=500,
            reason_phrase="ISE",
            content=b"err",
            headers=httpx.Headers(),
        )

        with pytest.raises(VectorStoreException, match="BM25"):
            await adapter.text_search(
                query_text="q", top_k=5, user_depts=["d"]
            )


class TestQdrantAdapterCheckFulltextIndex:
    """QdrantAdapter.check_fulltext_index 테스트."""

    def _make_adapter(self) -> tuple[QdrantAdapter, AsyncMock]:
        client = AsyncMock(spec=AsyncQdrantClient)
        settings = Settings(
            QDRANT_URL="http://test-qdrant:6333",
            QDRANT_COLLECTION="test-collection",
            QDRANT_CONTENT_FIELD="text_for_search",
        )
        with patch(
            "app.adapters.qdrant_adapter.AsyncQdrantClient", return_value=client
        ):
            adapter = QdrantAdapter(settings=settings)
        return adapter, client

    def _make_info(self, payload_schema: dict) -> AsyncMock:
        info = AsyncMock()
        info.payload_schema = payload_schema
        return info

    async def test_returns_true_when_text_index_exists(self):
        """text_for_search 필드에 text 타입 인덱스가 있으면 True."""
        adapter, client = self._make_adapter()
        field_info = AsyncMock()
        field_info.data_type = AsyncMock()
        field_info.data_type.value = "text"
        client.get_collection.return_value = self._make_info(
            {"text_for_search": field_info}
        )

        assert await adapter.check_fulltext_index() is True

    async def test_returns_false_when_field_missing(self):
        """text_for_search 필드 스키마가 없으면 False."""
        adapter, client = self._make_adapter()
        client.get_collection.return_value = self._make_info({})

        assert await adapter.check_fulltext_index() is False

    async def test_returns_false_when_not_text_type(self):
        """필드는 있지만 text 타입이 아니면 False."""
        adapter, client = self._make_adapter()
        field_info = AsyncMock()
        field_info.data_type = AsyncMock()
        field_info.data_type.value = "keyword"
        client.get_collection.return_value = self._make_info(
            {"text_for_search": field_info}
        )

        assert await adapter.check_fulltext_index() is False

    async def test_returns_false_on_connect_error(self):
        """Qdrant 연결 실패 시 False (예외 전파 없음)."""
        adapter, client = self._make_adapter()
        client.get_collection.side_effect = httpx.ConnectError("refused")

        assert await adapter.check_fulltext_index() is False

    async def test_returns_false_on_timeout(self):
        adapter, client = self._make_adapter()
        client.get_collection.side_effect = httpx.TimeoutException("timeout")

        assert await adapter.check_fulltext_index() is False

    async def test_returns_false_on_unexpected_response(self):
        adapter, client = self._make_adapter()
        client.get_collection.side_effect = UnexpectedResponse(
            status_code=500,
            reason_phrase="ISE",
            content=b"err",
            headers=httpx.Headers(),
        )

        assert await adapter.check_fulltext_index() is False


class TestFetchChunksByParents:
    """fetch_chunks_by_parents — 필터 구성·페이지네이션·빈 입력 (parent-document)."""

    def _make_adapter(self) -> tuple[QdrantAdapter, AsyncMock]:
        settings = Settings(
            QDRANT_URL="http://test-qdrant:6333",
            QDRANT_COLLECTION="test-collection",
            QDRANT_CONTENT_FIELD="text_for_search",
        )
        client = AsyncMock(spec=AsyncQdrantClient)
        with patch(
            "app.adapters.qdrant_adapter.AsyncQdrantClient",
            return_value=client,
        ):
            adapter = QdrantAdapter(settings=settings)
        return adapter, client

    def _point(self, point_id: int, parent_id, chunk_index: int) -> ScoredPoint:
        return ScoredPoint(
            id=point_id,
            version=1,
            score=0.0,
            payload={
                "text_for_search": f"chunk {chunk_index}",
                "doc_content_id": "dcA",
                "parent_id": parent_id,
                "chunk_index": chunk_index,
                "is_active": "Y",
            },
        )

    async def test_empty_input_skips_scroll(self):
        """입력이 비면 scroll 호출 없이 빈 리스트."""
        adapter, client = self._make_adapter()
        result = await adapter.fetch_chunks_by_parents({})
        assert result == []
        client.scroll.assert_not_called()

    async def test_filter_has_doc_parent_active(self):
        """필터에 doc_content_id == X, parent_id IN ids, is_active == 'Y' 포함."""
        from qdrant_client.models import FieldCondition, MatchAny, MatchValue

        adapter, client = self._make_adapter()
        client.scroll.return_value = ([self._point(1, 4, 10)], None)

        await adapter.fetch_chunks_by_parents({"dcA": [3, 4, 5]})

        client.scroll.assert_called_once()
        kwargs = client.scroll.call_args.kwargs
        flt = kwargs["scroll_filter"]
        assert (
            FieldCondition(
                key=PayloadField.DOC_CONTENT_ID, match=MatchValue(value="dcA")
            )
            in flt.must
        )
        assert (
            FieldCondition(
                key=PayloadField.PARENT_ID, match=MatchAny(any=[3, 4, 5])
            )
            in flt.must
        )
        assert (
            FieldCondition(
                key=PayloadField.IS_ACTIVE, match=MatchValue(value="Y")
            )
            in flt.must
        )
        assert kwargs["with_vectors"] is False

    async def test_pagination_aggregates_all_pages(self):
        """offset이 None 될 때까지 모든 페이지를 합친다."""
        adapter, client = self._make_adapter()
        client.scroll.side_effect = [
            ([self._point(1, 4, 10), self._point(2, 4, 11)], "cursor-1"),
            ([self._point(3, 5, 12)], None),
        ]

        result = await adapter.fetch_chunks_by_parents({"dcA": [4, 5]})

        assert client.scroll.call_count == 2
        assert {c["_point_id"] for c in result} == {1, 2, 3}
        # 반환 형태: content / metadata(_content_field 제외) / _point_id
        assert result[0]["content"] == "chunk 10"
        assert "parent_id" in result[0]["metadata"]
        assert "text_for_search" not in result[0]["metadata"]

    async def test_scroll_per_document(self):
        """서로 다른 문서 수만큼 scroll(병렬)이 호출된다."""
        adapter, client = self._make_adapter()
        client.scroll.return_value = ([self._point(1, 4, 10)], None)

        await adapter.fetch_chunks_by_parents({"dcA": [4], "dcB": [7]})

        assert client.scroll.call_count == 2
