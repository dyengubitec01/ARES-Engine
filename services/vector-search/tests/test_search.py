"""검색 엔드포인트 및 서비스 테스트."""

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
from app.adapters.mocks.mock_reranker import MockReranker
from app.adapters.mocks.mock_vector_store import MockVectorStore
from app.adapters.reranker_adapter import RerankerAdapter
from app.core.config import Settings, get_settings
from app.core.exceptions import RerankerException
from app.core.interfaces import (
    EmbeddingInterface,
    RerankerInterface,
    VectorStoreInterface,
)
from app.core.payload_fields import RESPONSE_METADATA_FIELDS, RESPONSE_METADATA_KEY_MAP
from app.main import create_app
from app.services.search_service import SearchService


# === 인터페이스 테스트 ===


class TestInterfaces:
    """추상 인터페이스가 올바르게 정의되는지 확인."""

    def test_mock_vector_store_implements_interface(self):
        """MockVectorStore가 VectorStoreInterface를 구현하는지 확인."""
        store = MockVectorStore()
        assert isinstance(store, VectorStoreInterface)

    def test_mock_reranker_implements_interface(self):
        """MockReranker가 RerankerInterface를 구현하는지 확인."""
        reranker = MockReranker()
        assert isinstance(reranker, RerankerInterface)


# === Mock 어댑터 테스트 ===


class TestMockVectorStore:
    """MockVectorStore 동작 테스트."""

    async def test_returns_correct_count(self):
        """요청한 top_k 만큼 결과를 반환하는지 확인."""
        store = MockVectorStore()
        results = await store.search(query_vector=[], top_k=5, user_depts=["test-dept"])
        assert len(results) == 5

    async def test_result_structure(self):
        """각 결과에 content, metadata, score가 포함되는지 확인."""
        store = MockVectorStore()
        results = await store.search(query_vector=[], top_k=1, user_depts=["test-dept"])
        item = results[0]
        assert "content" in item
        assert "metadata" in item
        assert "score" in item


class TestMockReranker:
    """MockReranker 동작 테스트."""

    async def test_returns_limited_by_top_k(self):
        """top_k 만큼만 결과를 반환하는지 확인."""
        reranker = MockReranker()
        texts = [f"text {i}" for i in range(10)]
        results = await reranker.rerank(query="test", texts=texts, top_k=3)
        assert len(results) == 3

    async def test_result_structure(self):
        """각 결과에 index, score, text가 포함되는지 확인."""
        reranker = MockReranker()
        results = await reranker.rerank(
            query="test", texts=["hello"], top_k=1
        )
        item = results[0]
        assert "index" in item
        assert "score" in item
        assert "text" in item

    async def test_sorted_by_score(self):
        """결과가 점수 내림차순으로 정렬되는지 확인."""
        reranker = MockReranker()
        texts = [f"text {i}" for i in range(5)]
        results = await reranker.rerank(query="test", texts=texts, top_k=5)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


# === SearchService 테스트 ===


class TestSearchService:
    """SearchService 테스트."""

    @pytest.fixture
    def mock_embedding(self):
        """MockEmbeddingAdapter fixture."""
        return MockEmbeddingAdapter()

    @pytest.fixture
    def service(self, mock_embedding):
        """SearchService fixture — embedding 포함."""
        return SearchService(
            embedding=mock_embedding,
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )

    async def test_search_returns_expected_structure(self, service):
        """검색 결과에 query, trace_id, results가 포함되는지 확인."""
        data = await service.search(
            query="테스트", user_depts=["test-dept"], search_k=10, top_k=3, trace_id="test-trace-id"
        )
        assert data["query"] == "테스트"
        assert data["trace_id"] == "test-trace-id"
        assert isinstance(data["results"], list)

    async def test_result_item_structure(self, service):
        """각 결과 아이템에 rank, score, content, metadata가 포함되는지 확인."""
        data = await service.search(
            query="test", user_depts=["test-dept"], search_k=10, top_k=3, trace_id="test-trace-id"
        )
        for item in data["results"]:
            assert "rank" in item
            assert "score" in item
            assert "content" in item
            assert "metadata" in item

    async def test_top_k_limits_results(self, service):
        """top_k가 최종 결과 수를 제한하는지 확인."""
        data = await service.search(
            query="test", user_depts=["test-dept"], search_k=20, top_k=3, trace_id="test-trace-id"
        )
        assert len(data["results"]) <= 3

    async def test_rank_starts_at_1(self, service):
        """rank가 1부터 시작하는지 확인."""
        data = await service.search(
            query="test", user_depts=["test-dept"], search_k=10, top_k=5, trace_id="test-trace-id"
        )
        ranks = [r["rank"] for r in data["results"]]
        assert ranks[0] == 1

    async def test_empty_results_skips_reranker(self):
        """벡터 검색 결과가 빈 리스트면 리랭킹 없이 빈 결과 반환."""

        class EmptyVectorStore(VectorStoreInterface):
            async def search(self, query_vector, top_k, user_depts, excluded_docs=None):
                return []

            async def text_search(self, query_text, top_k, user_depts, excluded_docs=None):
                return []

            async def check_fulltext_index(self) -> bool:
                return True

            async def fetch_chunks_by_parents(self, parents_by_doc):
                return []

        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=EmptyVectorStore(),
            reranker=MockReranker(),
        )
        data = await service.search(
            query="test", user_depts=["test-dept"], search_k=10, top_k=3, trace_id="test-trace-id"
        )
        assert data["results"] == []
        assert data["query"] == "test"
        assert data["trace_id"] == "test-trace-id"

    async def test_embed_called_with_query(self):
        """search() 호출 시 embedding.embed()가 쿼리 문자열로 호출되는지 확인."""
        mock_embed = AsyncMock(spec=EmbeddingInterface)
        mock_embed.embed.return_value = [0.1] * 1024
        service = SearchService(
            embedding=mock_embed,
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )
        await service.search(
            query="임베딩 테스트", user_depts=["test-dept"], search_k=10, top_k=3, trace_id="test-trace-id"
        )
        mock_embed.embed.assert_called_once_with("임베딩 테스트")

    async def test_embed_vector_passed_to_vector_store(self):
        """embed() 결과 벡터가 vector_store.search()에 전달되는지 확인."""
        expected_vector = [0.5] * 512
        mock_embed = AsyncMock(spec=EmbeddingInterface)
        mock_embed.embed.return_value = expected_vector

        mock_store = AsyncMock(spec=VectorStoreInterface)
        mock_store.search.return_value = []

        service = SearchService(
            embedding=mock_embed,
            vector_store=mock_store,
            reranker=MockReranker(),
        )
        await service.search(
            query="벡터 전달 테스트", user_depts=["test-dept"], search_k=5, top_k=3, trace_id="test-trace-id"
        )
        mock_store.search.assert_called_once_with(
            query_vector=expected_vector, top_k=5, user_depts=["test-dept"], excluded_docs=None
        )

    async def test_embedding_exception_propagates(self):
        """embed() 실패 시 EmbeddingException이 서비스 밖으로 전파되는지 확인."""
        from app.core.exceptions import EmbeddingException

        mock_embed = AsyncMock(spec=EmbeddingInterface)
        mock_embed.embed.side_effect = EmbeddingException(msg="API 실패")
        service = SearchService(
            embedding=mock_embed,
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )
        with pytest.raises(EmbeddingException, match="API 실패"):
            await service.search(
                query="실패 테스트", user_depts=["test-dept"], search_k=10, top_k=3, trace_id="test-trace-id"
            )

    async def test_response_metadata_contains_only_allowed_fields(self):
        """응답 metadata에 RESPONSE_METADATA_FIELDS에 정의된 필드만 포함된다."""
        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )
        result = await service.search(
            query="필드 제한 테스트", user_depts=["test-dept"], search_k=10, top_k=3, trace_id="test-trace-id"
        )
        for item in result["results"]:
            expected_keys = {RESPONSE_METADATA_KEY_MAP.get(f, f) for f in RESPONSE_METADATA_FIELDS}
            assert set(item["metadata"].keys()) <= expected_keys

    async def test_score_threshold_filters_low_scores(self):
        """score_threshold 미만인 결과는 제외된다."""

        class LowScoreReranker(RerankerInterface):
            async def rerank(self, query: str, texts: list[str], top_k: int):
                return [
                    {"index": 0, "score": 0.8, "text": texts[0]},
                    {"index": 1, "score": 0.05, "text": texts[1]},
                    {"index": 2, "score": 0.01, "text": texts[2]},
                ]

        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=LowScoreReranker(),
        )
        result = await service.search(
            query="threshold 테스트",
            user_depts=["test-dept"],
            search_k=10,
            top_k=3,
            trace_id="test-trace-id",
            score_threshold=0.1,
        )
        assert len(result["results"]) == 1
        assert result["results"][0]["score"] == 0.8

    async def test_score_threshold_zero_returns_all(self):
        """score_threshold=0.0이면 모든 결과를 반환한다."""
        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )
        result = await service.search(
            query="no filter 테스트",
            user_depts=["test-dept"],
            search_k=10,
            top_k=5,
            trace_id="test-trace-id",
            score_threshold=0.0,
        )
        assert len(result["results"]) == 5

    async def test_score_threshold_adjusts_rank(self):
        """score_threshold로 필터링 후 rank가 1부터 재정렬된다."""

        class MixedScoreReranker(RerankerInterface):
            async def rerank(self, query: str, texts: list[str], top_k: int):
                return [
                    {"index": 0, "score": 0.9, "text": texts[0]},
                    {"index": 1, "score": 0.005, "text": texts[1]},  # filtered
                    {"index": 2, "score": 0.5, "text": texts[2]},
                ]

        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MixedScoreReranker(),
        )
        result = await service.search(
            query="rank 테스트",
            user_depts=["test-dept"],
            search_k=10,
            top_k=3,
            trace_id="test-trace-id",
            score_threshold=0.01,
        )
        assert len(result["results"]) == 2
        assert result["results"][0]["rank"] == 1
        assert result["results"][1]["rank"] == 2


class TestRRFFuse:
    """SearchService._rrf_fuse 단위 테스트."""

    def _item(self, point_id: str, score: float = 0.9) -> dict:
        """RRF 입력용 검색 결과 dict를 생성한다."""
        return {
            "_point_id": point_id,
            "content": f"content-{point_id}",
            "metadata": {"doc_content_id": f"dc-{point_id}"},
            "score": score,
        }

    def test_both_empty_returns_empty(self):
        result = SearchService._rrf_fuse([], [])
        assert result == []

    def test_dense_only_preserves_order(self):
        """BM25가 비어 있으면 dense 순위 그대로, _source=dense."""
        dense = [self._item("A", 0.9), self._item("B", 0.8), self._item("C", 0.7)]
        result = SearchService._rrf_fuse(dense, [])
        assert [x["_point_id"] for x in result] == ["A", "B", "C"]
        assert all(x["_source"] == "dense" for x in result)
        assert result[0]["_rrf_score"] == pytest.approx(1.0 / 61)
        assert result[1]["_rrf_score"] == pytest.approx(1.0 / 62)

    def test_bm25_only_preserves_order(self):
        """dense가 비어 있으면 bm25 순위 그대로, _source=bm25."""
        bm25 = [self._item("X", 12.3), self._item("Y", 10.0)]
        result = SearchService._rrf_fuse([], bm25)
        assert [x["_point_id"] for x in result] == ["X", "Y"]
        assert all(x["_source"] == "bm25" for x in result)

    def test_bm25_only_preserves_bm25_score(self):
        """BM25-only 아이템은 원본 BM25 score를 그대로 유지."""
        bm25 = [self._item("X", 12.3)]
        result = SearchService._rrf_fuse([], bm25)
        assert result[0]["score"] == 12.3

    def test_overlap_sums_and_marks_source(self):
        """양쪽에 있는 문서는 _rrf_score 합산 + _source=dense+bm25."""
        dense = [self._item("A", 0.9), self._item("B", 0.8)]
        bm25 = [self._item("B", 11.0), self._item("C", 10.0)]
        result = SearchService._rrf_fuse(dense, bm25, k=60)

        by_id = {x["_point_id"]: x for x in result}
        assert by_id["B"]["_source"] == "dense+bm25"
        assert by_id["A"]["_source"] == "dense"
        assert by_id["C"]["_source"] == "bm25"
        # B: dense rank 2 + bm25 rank 1 = 1/62 + 1/61
        assert by_id["B"]["_rrf_score"] == pytest.approx(1.0 / 62 + 1.0 / 61)

    def test_overlap_preserves_dense_score(self):
        """양쪽에 있으면 dense의 원본 score를 보존한다(BM25 score가 아님)."""
        dense = [self._item("A", 0.9)]
        bm25 = [self._item("A", 15.5)]  # 같은 point_id, 다른 score
        result = SearchService._rrf_fuse(dense, bm25)
        assert len(result) == 1
        assert result[0]["score"] == 0.9

    def test_sorted_by_rrf_score_desc(self):
        """결과는 _rrf_score 내림차순으로 정렬된다."""
        dense = [
            self._item("A"), self._item("B"), self._item("C"),
        ]
        bm25 = [
            self._item("C"), self._item("A"), self._item("D"),
        ]
        result = SearchService._rrf_fuse(dense, bm25)
        scores = [x["_rrf_score"] for x in result]
        assert scores == sorted(scores, reverse=True)
        # 양쪽 모두 있는 A와 C가 D, B보다 위
        top_two = {result[0]["_point_id"], result[1]["_point_id"]}
        assert top_two == {"A", "C"}

    def test_rrf_k_parameter(self):
        """k 파라미터가 RRF 점수 계산에 반영된다."""
        dense = [self._item("A")]
        result = SearchService._rrf_fuse(dense, [], k=100)
        assert result[0]["_rrf_score"] == pytest.approx(1.0 / 101)

    def test_missing_point_id_skipped(self):
        """_point_id가 없는 아이템은 무시한다(방어적 처리)."""
        dense = [{"content": "no point id", "metadata": {}, "score": 0.5}]
        bm25 = [self._item("X")]
        result = SearchService._rrf_fuse(dense, bm25)
        assert len(result) == 1
        assert result[0]["_point_id"] == "X"


class TestHybridSearchPipeline:
    """HYBRID_SEARCH_ENABLED 분기 및 실패 매트릭스 테스트."""

    def _hybrid_settings(self, enabled: bool = True) -> Settings:
        return Settings(
            _env_file=None,
            HYBRID_SEARCH_ENABLED=enabled,
            RRF_K=60,
        )

    def _make_result(self, point_id: str, score: float = 0.9) -> dict:
        return {
            "_point_id": point_id,
            "content": f"content-{point_id}",
            "metadata": {"doc_content_id": f"dc-{point_id}"},
            "score": score,
        }

    def _make_service(
        self,
        *,
        dense_return=None,
        bm25_return=None,
        dense_side_effect=None,
        bm25_side_effect=None,
        hybrid_enabled: bool = True,
    ) -> tuple[SearchService, AsyncMock]:
        mock_embed = AsyncMock(spec=EmbeddingInterface)
        mock_embed.embed.return_value = [0.1] * 1024

        mock_store = AsyncMock(spec=VectorStoreInterface)
        if dense_side_effect is not None:
            mock_store.search.side_effect = dense_side_effect
        else:
            mock_store.search.return_value = dense_return or []
        if bm25_side_effect is not None:
            mock_store.text_search.side_effect = bm25_side_effect
        else:
            mock_store.text_search.return_value = bm25_return or []

        service = SearchService(
            embedding=mock_embed,
            vector_store=mock_store,
            reranker=MockReranker(),
            settings=self._hybrid_settings(enabled=hybrid_enabled),
        )
        return service, mock_store

    async def test_hybrid_disabled_calls_dense_only(self):
        """HYBRID_SEARCH_ENABLED=False면 text_search를 호출하지 않는다."""
        service, store = self._make_service(
            dense_return=[self._make_result("A")],
            hybrid_enabled=False,
        )
        await service.search(
            query="test", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        store.search.assert_called_once()
        store.text_search.assert_not_called()

    async def test_hybrid_enabled_calls_both(self):
        """HYBRID_SEARCH_ENABLED=True면 dense와 BM25 둘 다 호출된다."""
        service, store = self._make_service(
            dense_return=[self._make_result("A"), self._make_result("B")],
            bm25_return=[self._make_result("B"), self._make_result("C")],
        )
        await service.search(
            query="test", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        store.search.assert_called_once()
        store.text_search.assert_called_once()

    async def test_hybrid_bm25_failure_falls_back_to_dense(self, caplog):
        """BM25 실패 시 WARN 로그 후 dense-only로 진행."""
        from app.core.exceptions import VectorStoreException

        service, _ = self._make_service(
            dense_return=[self._make_result("A"), self._make_result("B")],
            bm25_side_effect=VectorStoreException(msg="bm25 down"),
        )
        with caplog.at_level(logging.WARNING):
            data = await service.search(
                query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
            )
        assert "BM25 검색 실패" in caplog.text
        assert len(data["results"]) > 0

    async def test_hybrid_dense_failure_falls_back_to_bm25(self, caplog):
        """Dense 실패 시 WARN 로그 후 BM25-only로 진행."""
        from app.core.exceptions import VectorStoreException

        service, _ = self._make_service(
            dense_side_effect=VectorStoreException(msg="qdrant down"),
            bm25_return=[self._make_result("X"), self._make_result("Y")],
        )
        with caplog.at_level(logging.WARNING):
            data = await service.search(
                query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
            )
        assert "Dense 검색 실패" in caplog.text
        assert len(data["results"]) > 0

    async def test_hybrid_both_failures_raise(self):
        """양쪽 모두 실패하면 VectorStoreException이 전파된다."""
        from app.core.exceptions import VectorStoreException

        service, _ = self._make_service(
            dense_side_effect=VectorStoreException(msg="qdrant down"),
            bm25_side_effect=VectorStoreException(msg="bm25 down"),
        )
        with pytest.raises(VectorStoreException, match="Hybrid"):
            await service.search(
                query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
            )

    async def test_hybrid_response_strips_internal_fields(self):
        """최종 응답에 _point_id, _rrf_score, _source 등 내부 필드가 노출되지 않는다."""
        service, _ = self._make_service(
            dense_return=[self._make_result("A"), self._make_result("B")],
            bm25_return=[self._make_result("A"), self._make_result("C")],
        )
        data = await service.search(
            query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        for item in data["results"]:
            assert "_point_id" not in item
            assert "_rrf_score" not in item
            assert "_source" not in item
            assert "_point_id" not in item.get("metadata", {})

    async def test_hybrid_reranker_fallback_uses_original_score(self):
        """Reranker 실패 시 fallback 응답의 score가 RRF 점수가 아닌 원본 score."""
        dense_results = [self._make_result("A", score=0.87)]
        bm25_results = [self._make_result("A", score=11.2)]

        # 리랭커 실패 시키기
        failing_reranker = AsyncMock(spec=RerankerInterface)
        failing_reranker.rerank.side_effect = RerankerException(msg="down")

        mock_embed = AsyncMock(spec=EmbeddingInterface)
        mock_embed.embed.return_value = [0.1] * 1024
        mock_store = AsyncMock(spec=VectorStoreInterface)
        mock_store.search.return_value = dense_results
        mock_store.text_search.return_value = bm25_results

        service = SearchService(
            embedding=mock_embed,
            vector_store=mock_store,
            reranker=failing_reranker,
            settings=self._hybrid_settings(enabled=True),
        )
        data = await service.search(
            query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        assert data.get("fallback") is True
        assert len(data["results"]) == 1
        # dense score(0.87) 보존, RRF 점수(0.03 수준) 노출 금지
        assert data["results"][0]["score"] == 0.87

    async def test_hybrid_span_input_includes_search_mode(self):
        """vector-search span input에 search_mode가 기록된다."""
        service, _ = self._make_service(
            dense_return=[self._make_result("A")],
            bm25_return=[self._make_result("A")],
        )
        with patch("app.services.search_service.observe") as mock_observe:
            from unittest.mock import MagicMock
            mock_observe.return_value.__enter__.return_value = MagicMock()
            mock_observe.return_value.__exit__.return_value = None
            await service.search(
                query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
            )
        vector_search_calls = [
            c for c in mock_observe.call_args_list
            if c.kwargs.get("name") == "vector-search"
        ]
        assert len(vector_search_calls) == 1
        assert vector_search_calls[0].kwargs["input"]["search_mode"] == "hybrid"

    async def test_hybrid_creates_child_spans(self):
        """hybrid 모드에서 dense-search / bm25-search / rrf-fusion child span이 생성된다."""
        service, _ = self._make_service(
            dense_return=[self._make_result("A"), self._make_result("B")],
            bm25_return=[self._make_result("A"), self._make_result("C")],
        )
        with patch("app.services.search_service.observe") as mock_observe:
            from unittest.mock import MagicMock
            mock_observe.return_value.__enter__.return_value = MagicMock()
            mock_observe.return_value.__exit__.return_value = None
            await service.search(
                query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
            )

        span_names = [
            c.kwargs.get("name") for c in mock_observe.call_args_list
        ]
        assert "vector-search" in span_names
        assert "dense-search" in span_names
        assert "bm25-search" in span_names
        assert "rrf-fusion" in span_names

    async def test_dense_only_mode_has_no_child_spans(self):
        """hybrid OFF면 dense-search/bm25-search/rrf-fusion span이 생성되지 않는다."""
        service, _ = self._make_service(
            dense_return=[self._make_result("A")],
            hybrid_enabled=False,
        )
        with patch("app.services.search_service.observe") as mock_observe:
            from unittest.mock import MagicMock
            mock_observe.return_value.__enter__.return_value = MagicMock()
            mock_observe.return_value.__exit__.return_value = None
            await service.search(
                query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
            )

        span_names = [
            c.kwargs.get("name") for c in mock_observe.call_args_list
        ]
        assert "vector-search" in span_names
        assert "dense-search" not in span_names
        assert "bm25-search" not in span_names
        assert "rrf-fusion" not in span_names

    async def test_rrf_fusion_span_input_has_counts(self):
        """rrf-fusion span input에 dense_count, bm25_count, rrf_k가 포함된다."""
        service, _ = self._make_service(
            dense_return=[self._make_result("A"), self._make_result("B")],
            bm25_return=[self._make_result("X")],
        )
        with patch("app.services.search_service.observe") as mock_observe:
            from unittest.mock import MagicMock
            mock_observe.return_value.__enter__.return_value = MagicMock()
            mock_observe.return_value.__exit__.return_value = None
            await service.search(
                query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
            )

        rrf_calls = [
            c for c in mock_observe.call_args_list
            if c.kwargs.get("name") == "rrf-fusion"
        ]
        assert len(rrf_calls) == 1
        input_dict = rrf_calls[0].kwargs["input"]
        assert input_dict["dense_count"] == 2
        assert input_dict["bm25_count"] == 1
        assert input_dict["rrf_k"] == 60

    async def test_runtime_settings_mutation_propagates_to_service(self):
        """Settings 객체 mutation이 SearchService 동작에 즉시 반영된다.

        startup 훅(disable_hybrid_if_fulltext_index_missing)이 settings를
        mutate했을 때 SearchService가 다음 호출부터 dense-only로 동작해야 함.
        이 테스트는 런타임 mutation → 동작 변경 경로를 실제로 검증한다.
        """
        settings = self._hybrid_settings(enabled=True)
        mock_embed = AsyncMock(spec=EmbeddingInterface)
        mock_embed.embed.return_value = [0.1] * 1024
        mock_store = AsyncMock(spec=VectorStoreInterface)
        mock_store.search.return_value = [self._make_result("A")]
        mock_store.text_search.return_value = [self._make_result("B")]

        service = SearchService(
            embedding=mock_embed,
            vector_store=mock_store,
            reranker=MockReranker(),
            settings=settings,  # ← 같은 객체를 서비스와 mutation 지점이 공유
        )

        # 1회: hybrid 모드 — 양쪽 호출
        await service.search(
            query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t1"
        )
        assert mock_store.search.call_count == 1
        assert mock_store.text_search.call_count == 1

        # 런타임 mutation: startup 훅이 하는 것과 동일
        settings.HYBRID_SEARCH_ENABLED = False

        # 2회: dense-only로 변경됨 — text_search는 더 이상 호출 안 됨
        await service.search(
            query="t", user_depts=["d"], search_k=5, top_k=3, trace_id="t2"
        )
        assert mock_store.search.call_count == 2
        assert mock_store.text_search.call_count == 1  # 증가 없음


# === Parent-document 확장 테스트 ===


class TestParentExpansion:
    """PARENT_EXPANSION_ENABLED 분기 및 parent ±1 확장/병합/방어로직 테스트."""

    def _settings(self, enabled: bool = True) -> Settings:
        return Settings(_env_file=None, PARENT_EXPANSION_ENABLED=enabled)

    def _candidate(self, point_id, doc_id, parent_id, *, chunk_index=0, score=0.9):
        """후보 청크 (실 payload와 동일하게 문자열 키 metadata 사용)."""
        meta = {
            "doc_content_id": doc_id,
            "chunk_index": chunk_index,
            "original_filename": f"{doc_id}.pdf",
            "location_context": f"p{parent_id}",
            "text_preview": "preview",
            "is_active": "Y",
        }
        if parent_id is not None:
            meta["parent_id"] = parent_id
        return {
            "_point_id": point_id,
            "content": f"{point_id} content",
            "metadata": meta,
            "score": score,
        }

    def _parent_chunk(self, doc_id, parent_id, chunk_index, point_id=None):
        return {
            "_point_id": point_id or f"{doc_id}-p{parent_id}-c{chunk_index}",
            "content": f"{doc_id} p{parent_id} c{chunk_index}",
            "metadata": {
                "doc_content_id": doc_id,
                "parent_id": parent_id,
                "chunk_index": chunk_index,
                "original_filename": f"{doc_id}.pdf",
                "location_context": f"p{parent_id}",
                "text_preview": "preview",
                "is_active": "Y",
            },
        }

    def _make_service(self, *, candidates, rerank_return, fetch_return=None, enabled=True):
        mock_embed = AsyncMock(spec=EmbeddingInterface)
        mock_embed.embed.return_value = [0.1] * 1024
        mock_store = AsyncMock(spec=VectorStoreInterface)
        mock_store.search.return_value = candidates
        mock_store.fetch_chunks_by_parents.return_value = fetch_return or []
        mock_reranker = AsyncMock(spec=RerankerInterface)
        mock_reranker.rerank.return_value = rerank_return
        service = SearchService(
            embedding=mock_embed,
            vector_store=mock_store,
            reranker=mock_reranker,
            settings=self._settings(enabled),
        )
        return service, mock_store

    async def test_flag_off_no_expansion(self):
        """PARENT_EXPANSION_ENABLED=False면 확장하지 않고 청크 결과 그대로."""
        cands = [self._candidate("A", "dcA", 4)]
        rerank = [{"index": 0, "score": 0.9, "text": "rerank text A"}]
        service, store = self._make_service(
            candidates=cands, rerank_return=rerank, enabled=False
        )
        data = await service.search(
            query="q", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        store.fetch_chunks_by_parents.assert_not_called()
        assert len(data["results"]) == 1
        assert data["results"][0]["content"] == "rerank text A"

    async def test_expansion_merges_parent_chunks(self):
        """parent_id 있는 시드 → parent N-1,N,N+1 모든 청크 회수·병합."""
        cands = [self._candidate("A", "dcA", 4)]
        rerank = [{"index": 0, "score": 0.9, "text": "A"}]
        fetch = [
            self._parent_chunk("dcA", 3, 31),
            self._parent_chunk("dcA", 3, 30),
            self._parent_chunk("dcA", 4, 40),
            self._parent_chunk("dcA", 4, 41),
            self._parent_chunk("dcA", 5, 50),
        ]
        service, store = self._make_service(
            candidates=cands, rerank_return=rerank, fetch_return=fetch
        )
        data = await service.search(
            query="q", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        store.fetch_chunks_by_parents.assert_called_once_with({"dcA": [3, 4, 5]})
        assert len(data["results"]) == 3  # parent 3,4,5
        p3 = data["results"][0]
        # chunk_index 오름차순 병합 (30 → 31)
        assert p3["content"] == "dcA p3 c30\ndcA p3 c31"
        # 응답 metadata엔 parent_id 미노출, doc_id 매핑 적용
        assert "parent_id" not in p3["metadata"]
        assert p3["metadata"]["doc_id"] == "dcA"

    async def test_defensive_passthrough_for_missing_parent_id(self):
        """parent_id 없는 청크는 확장 없이 통과(혼재 컬렉션 방어로직)."""
        cands = [self._candidate("A", "dcA", None)]
        rerank = [{"index": 0, "score": 0.8, "text": "plain A"}]
        service, store = self._make_service(candidates=cands, rerank_return=rerank)
        data = await service.search(
            query="q", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        store.fetch_chunks_by_parents.assert_not_called()
        assert len(data["results"]) == 1
        assert data["results"][0]["content"] == "plain A"

    async def test_mixed_expand_and_passthrough(self):
        """parent_id 있는 파일은 확장, 없는 파일은 통과 — 한 결과에 공존."""
        cands = [
            self._candidate("A", "dcA", 4, score=0.9),
            self._candidate("B", "dcB", None, score=0.5),
        ]
        rerank = [
            {"index": 0, "score": 0.9, "text": "A"},
            {"index": 1, "score": 0.5, "text": "plain B"},
        ]
        fetch = [self._parent_chunk("dcA", 4, 40)]
        service, store = self._make_service(
            candidates=cands, rerank_return=rerank, fetch_return=fetch
        )
        data = await service.search(
            query="q", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        store.fetch_chunks_by_parents.assert_called_once_with({"dcA": [3, 4, 5]})
        contents = [r["content"] for r in data["results"]]
        assert any("dcA p4 c40" in c for c in contents)  # 확장된 parent
        assert contents[-1] == "plain B"  # 통과 청크가 더 낮은 score → 뒤

    async def test_dedup_overlapping_parents(self):
        """인접 시드의 ±1 범위가 겹치면 (doc, parent_id)/point_id로 dedup."""
        cands = [
            self._candidate("A", "dcA", 4, chunk_index=40, score=0.9),
            self._candidate("B", "dcA", 5, chunk_index=50, score=0.7),
        ]
        rerank = [
            {"index": 0, "score": 0.9, "text": "A"},
            {"index": 1, "score": 0.7, "text": "B"},
        ]
        fetch = [
            self._parent_chunk("dcA", 3, 30),
            self._parent_chunk("dcA", 4, 40),
            self._parent_chunk("dcA", 5, 50, point_id="dup"),
            self._parent_chunk("dcA", 5, 50, point_id="dup"),  # 중복 point_id
            self._parent_chunk("dcA", 6, 60),
        ]
        service, store = self._make_service(
            candidates=cands, rerank_return=rerank, fetch_return=fetch
        )
        data = await service.search(
            query="q", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        # 두 시드 ±1 합집합 = {3,4,5,6}
        store.fetch_chunks_by_parents.assert_called_once_with({"dcA": [3, 4, 5, 6]})
        assert len(data["results"]) == 4  # parent 3,4,5,6
        p5 = [r for r in data["results"] if "p5" in r["content"]][0]
        assert p5["content"] == "dcA p5 c50"  # 중복 청크 1개로

    async def test_expansion_error_falls_back_to_chunks(self):
        """확장 중 오류가 나도 기본(청크) 결과로 폴백한다(요청 안 죽음)."""
        cands = [self._candidate("A", "dcA", 4)]
        rerank = [{"index": 0, "score": 0.9, "text": "chunk A"}]
        service, store = self._make_service(candidates=cands, rerank_return=rerank)
        store.fetch_chunks_by_parents.side_effect = RuntimeError("qdrant down")
        data = await service.search(
            query="q", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        assert len(data["results"]) == 1
        assert data["results"][0]["content"] == "chunk A"  # 청크 폴백

    async def test_malformed_parent_id_passthrough(self):
        """parent_id가 빈 문자열/비숫자면 크래시 없이 통과(확장 안 함)."""
        cands = [self._candidate("A", "dcA", "")]  # parent_id="" 이상치
        rerank = [{"index": 0, "score": 0.9, "text": "chunk A"}]
        service, store = self._make_service(candidates=cands, rerank_return=rerank)
        data = await service.search(
            query="q", user_depts=["d"], search_k=5, top_k=3, trace_id="t"
        )
        store.fetch_chunks_by_parents.assert_not_called()
        assert len(data["results"]) == 1
        assert data["results"][0]["content"] == "chunk A"


# === 엔드포인트 테스트 ===


class TestSearchEndpoint:
    """POST /v1/search 엔드포인트 테스트."""

    async def test_search_success(self, app):
        """정상 검색 요청이 RAG100000을 반환하는지 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "테스트 쿼리", "user_depts": ["test-dept-uuid"]}
            )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "RAG100000"
        assert data["msg"] == "검색 성공"
        assert "data" in data

    async def test_search_response_data_structure(self, app):
        """응답 data에 query, trace_id, results가 포함되는지 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "구조 테스트", "user_depts": ["test-dept-uuid"]}
            )
        result_data = response.json()["data"]
        assert result_data["query"] == "구조 테스트"
        assert "trace_id" in result_data
        assert isinstance(result_data["results"], list)

    async def test_search_with_custom_top_k(self, app):
        """top_k를 커스텀으로 지정할 수 있는지 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search",
                json={"query": "top_k 테스트", "user_depts": ["test-dept-uuid"], "top_k": 2, "search_k": 10},
            )
        results = response.json()["data"]["results"]
        assert len(results) <= 2

    async def test_search_default_params_from_settings(self, app):
        """top_k, search_k 미지정 시 Settings 기본값이 적용되는지 확인."""
        settings = get_settings()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "기본값 테스트", "user_depts": ["test-dept-uuid"]}
            )
        results = response.json()["data"]["results"]
        assert len(results) <= settings.TOP_K

    async def test_search_result_item_fields(self, app):
        """결과 아이템에 rank, score, content, metadata가 포함되는지 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "필드 테스트", "user_depts": ["test-dept-uuid"]}
            )
        item = response.json()["data"]["results"][0]
        assert "rank" in item
        assert "score" in item
        assert "content" in item
        assert "metadata" in item

    async def test_missing_query_returns_400(self, app):
        """query 누락 시 400 에러(RAG100020) 반환 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/search", json={})
        assert response.status_code == 400
        assert response.json()["code"] == "RAG100020"

    async def test_missing_user_depts_returns_400(self, app):
        """user_depts 누락 시 400 에러(RAG100020) 반환 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "테스트"}
            )
        assert response.status_code == 400
        assert response.json()["code"] == "RAG100020"

    async def test_empty_user_depts_returns_400(self, app):
        """user_depts가 빈 리스트이면 400 에러(RAG100020) 반환 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "테스트", "user_depts": []}
            )
        assert response.status_code == 400
        assert response.json()["code"] == "RAG100020"

    async def test_string_user_depts_returns_validation_error(self, app):
        """user_depts에 문자열을 전달하면 validation error(RAG100020)를 반환한다."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "테스트", "user_depts": "single-string"}
            )
        assert response.status_code == 400
        assert response.json()["code"] == "RAG100020"

    async def test_search_with_excluded_docs(self, app):
        """excluded_docs를 포함한 검색 요청이 정상 응답을 반환한다."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search",
                json={
                    "query": "제외 테스트",
                    "user_depts": ["test-dept-uuid"],
                    "excluded_docs": ["dc-0001", "dc-0042"],
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "RAG100000"

    async def test_search_without_excluded_docs(self, app):
        """excluded_docs 미전달 시에도 정상 응답을 반환한다."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search",
                json={"query": "기본 테스트", "user_depts": ["test-dept-uuid"]},
            )
        assert response.status_code == 200
        assert response.json()["code"] == "RAG100000"


# === DI 바인딩 테스트 ===


class TestDIBinding:
    """create_app() DI 바인딩 테스트."""

    @pytest.fixture(autouse=True)
    def _clear_settings_cache(self):
        """테스트 전후 Settings 캐시를 정리한다."""
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_always_uses_real_adapters(self):
        """APP_ENV에 관계없이 실제 어댑터가 주입되는지 확인."""
        from app.adapters.embedding_adapter import EmbeddingAdapter
        from app.adapters.qdrant_adapter import QdrantAdapter

        with patch.dict("os.environ", {"APP_ENV": "dev"}, clear=False):
            get_settings.cache_clear()
            test_app = create_app()
        service = test_app.state.search_service
        assert isinstance(service._embedding, EmbeddingAdapter)
        assert isinstance(service._vector_store, QdrantAdapter)
        assert isinstance(service._reranker, RerankerAdapter)


# === 리랭커 파이프라인 통합 테스트 ===


class TestRerankerPipelineIntegration:
    """RerankerAdapter를 SearchService에 통합한 파이프라인 테스트."""

    def _make_settings(self, **overrides) -> Settings:
        """테스트용 Settings 인스턴스를 생성한다."""
        defaults = {
            "RERANKER_URL": "http://test-server:8011/rerank",
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

    def _make_reranker_response(self, items=None):
        """리랭커 API 성공 응답 mock을 생성한다."""
        if items is None:
            items = [
                {"index": 1, "text": "문서2", "score": 0.95},
                {"index": 0, "text": "문서1", "score": 0.42},
                {"index": 2, "text": "문서3", "score": 0.10},
            ]
        request = httpx.Request("POST", "http://test-server:8011/rerank")
        return httpx.Response(
            status_code=200,
            json={"value": items, "Count": len(items)},
            request=request,
        )

    async def test_pipeline_with_reranker_adapter(self):
        """RerankerAdapter 주입 시 전체 파이프라인이 정상 동작한다."""
        settings = self._make_settings()
        response = self._make_reranker_response()

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)

            service = SearchService(
                embedding=MockEmbeddingAdapter(),
                vector_store=MockVectorStore(),
                reranker=RerankerAdapter(settings),
            )
            result = await service.search(
                query="테스트", user_depts=["test-dept"], search_k=10, top_k=3, trace_id="test-trace-id"
            )

        assert result["query"] == "테스트"
        assert result["trace_id"] == "test-trace-id"
        assert len(result["results"]) == 3

    async def test_pipeline_result_has_metadata(self):
        """리랭커 결과가 원본 벡터 검색 결과의 metadata를 올바르게 매핑한다."""
        settings = self._make_settings()
        expected = MockVectorStore.build_result(0)
        expected_metadata = {
            RESPONSE_METADATA_KEY_MAP.get(k, k): v
            for k, v in expected["metadata"].items()
            if k in RESPONSE_METADATA_FIELDS
        }
        items = [
            {"index": 0, "text": expected["content"], "score": 0.90},
        ]
        response = self._make_reranker_response(items=items)

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)

            service = SearchService(
                embedding=MockEmbeddingAdapter(),
                vector_store=MockVectorStore(),
                reranker=RerankerAdapter(settings),
            )
            result = await service.search(
                query="매핑 테스트", user_depts=["test-dept"], search_k=10, top_k=1, trace_id="test-trace-id"
            )

        item = result["results"][0]
        assert item["rank"] == 1
        assert item["score"] == 0.90
        assert item["content"] == expected["content"]
        assert item["metadata"] == expected_metadata

    async def test_fallback_returns_results_on_reranker_failure(self):
        """리랭커 장애 시 Fallback으로 1차 검색 결과가 반환된다."""
        settings = self._make_settings()

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(
                post_side_effect=httpx.TimeoutException("timeout"),
            )

            service = SearchService(
                embedding=MockEmbeddingAdapter(),
                vector_store=MockVectorStore(),
                reranker=RerankerAdapter(settings),
            )
            result = await service.search(
                query="에러 테스트", user_depts=["test-dept"], search_k=10, top_k=3, trace_id="test-trace-id"
            )

        assert result["fallback"] is True
        assert len(result["results"]) == 3
        assert result["query"] == "에러 테스트"
        assert result["trace_id"] == "test-trace-id"

    async def test_endpoint_fallback_on_reranker_error(self, app):
        """엔드포인트에서 리랭커 장애 시 Fallback으로 HTTP 200 + RAG100000 응답을 반환한다."""
        mock_reranker = AsyncMock(spec=RerankerInterface)
        mock_reranker.rerank.side_effect = RerankerException(msg="테스트 에러")
        app.state.search_service._reranker = mock_reranker

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/search", json={"query": "에러 테스트", "user_depts": ["test-dept-uuid"]}
            )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "RAG100000"
        assert body["data"]["fallback"] is True
        assert len(body["data"]["results"]) > 0

    async def test_fallback_applies_top_k(self):
        """Fallback 결과가 top_k개로 슬라이싱된다."""
        mock_reranker = AsyncMock(spec=RerankerInterface)
        mock_reranker.rerank.side_effect = RerankerException(msg="장애")

        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=mock_reranker,
        )
        result = await service.search(
            query="슬라이싱 테스트", user_depts=["test-dept"], search_k=10, top_k=2, trace_id="test-trace-id"
        )
        assert result["fallback"] is True
        assert len(result["results"]) == 2
        assert result["results"][0]["rank"] == 1
        assert result["results"][1]["rank"] == 2

    async def test_fallback_has_correct_metadata(self):
        """Fallback 결과의 metadata가 RESPONSE_METADATA_FIELDS만 포함한다."""
        mock_reranker = AsyncMock(spec=RerankerInterface)
        mock_reranker.rerank.side_effect = RerankerException(msg="장애")

        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=mock_reranker,
        )
        result = await service.search(
            query="메타데이터 테스트", user_depts=["test-dept"], search_k=10, top_k=1, trace_id="test-trace-id"
        )
        expected = MockVectorStore.build_result(0)
        expected_metadata = {
            RESPONSE_METADATA_KEY_MAP.get(k, k): v
            for k, v in expected["metadata"].items()
            if k in RESPONSE_METADATA_FIELDS
        }
        item = result["results"][0]
        assert item["metadata"] == expected_metadata
        assert item["content"] == expected["content"]
        assert isinstance(item["score"], float)

    async def test_fallback_logs_warning(self, caplog):
        """Fallback 활성화 시 WARNING 레벨 로그가 기록된다."""
        mock_reranker = AsyncMock(spec=RerankerInterface)
        mock_reranker.rerank.side_effect = RerankerException(msg="timeout")

        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=mock_reranker,
        )
        with caplog.at_level(logging.WARNING, logger="app.services.search_service"):
            await service.search(
                query="로그 테스트", user_depts=["test-dept"], search_k=10, top_k=3, trace_id="test-trace-id"
            )
        assert "Fallback" in caplog.text
        assert "로그 테스트" in caplog.text

    async def test_normal_search_no_fallback_flag(self):
        """정상 리랭킹 시 응답에 fallback 키가 없다."""
        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )
        result = await service.search(
            query="정상 테스트", user_depts=["test-dept"], search_k=10, top_k=3, trace_id="test-trace-id"
        )
        assert "fallback" not in result
        assert len(result["results"]) == 3
