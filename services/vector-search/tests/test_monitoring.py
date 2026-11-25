"""Langfuse 모니터링 모듈 테스트."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.monitoring import (
    LangfuseMiddleware,
    _reset_langfuse_client,
    get_langfuse_client,
    shutdown_langfuse,
)
from app.main import create_app


@pytest.fixture(autouse=True)
def _isolate_langfuse_client():
    """각 테스트 전후로 전역 Langfuse 클라이언트를 리셋한다."""
    _reset_langfuse_client()
    yield
    _reset_langfuse_client()


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """각 테스트 전후로 Settings 캐시를 정리한다."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# === get_langfuse_client 테스트 ===


class TestGetLangfuseClient:
    """get_langfuse_client() 함수 테스트."""

    def test_disabled_returns_none(self, monkeypatch):
        """LANGFUSE_ENABLED=false일 때 None을 반환하는지 확인."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "false")
        result = get_langfuse_client()
        assert result is None

    def test_empty_key_returns_none(self, monkeypatch):
        """LANGFUSE_ENABLED=true이지만 LANGFUSE_PUBLIC_KEY가 비어있으면 None 반환."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "true")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
        result = get_langfuse_client()
        assert result is None

    def test_enabled_with_valid_key(self, monkeypatch):
        """유효한 설정 시 Langfuse 인스턴스를 반환하는지 확인."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "true")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-key")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-key")
        monkeypatch.setenv("LANGFUSE_HOST", "https://test.langfuse.com")

        mock_langfuse_instance = MagicMock()
        mock_langfuse_cls = MagicMock(return_value=mock_langfuse_instance)
        with patch.dict(
            "sys.modules",
            {"langfuse": MagicMock(Langfuse=mock_langfuse_cls)},
        ):
            result = get_langfuse_client()

        assert result is mock_langfuse_instance

    def test_creation_failure_returns_none(self, monkeypatch):
        """Langfuse 클라이언트 생성 실패 시 None을 반환하는지 확인."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "true")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-key")
        monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-key")

        with patch.dict(
            "sys.modules",
            {"langfuse": MagicMock(Langfuse=MagicMock(side_effect=Exception("연결 실패")))},
        ):
            result = get_langfuse_client()

        assert result is None


# === shutdown_langfuse 테스트 ===


class TestShutdownLangfuse:
    """shutdown_langfuse() 함수 테스트."""

    def test_flushes_client(self):
        """shutdown 시 flush가 호출되고 클라이언트가 None으로 리셋되는지 확인."""
        import app.core.monitoring as mod

        mock_client = MagicMock()
        mod._langfuse_client = mock_client

        shutdown_langfuse()

        mock_client.flush.assert_called_once()
        assert mod._langfuse_client is None

    def test_noop_when_disabled(self):
        """클라이언트가 None일 때 에러 없이 종료되는지 확인."""
        shutdown_langfuse()  # _langfuse_client is None by fixture

    def test_flush_error_handled(self):
        """flush 실패 시에도 정상 종료되는지 확인."""
        import app.core.monitoring as mod

        mock_client = MagicMock()
        mock_client.flush.side_effect = Exception("flush 실패")
        mod._langfuse_client = mock_client

        shutdown_langfuse()  # 예외 발생하지 않아야 함


# === LangfuseMiddleware 테스트 ===


class TestLangfuseMiddleware:
    """LangfuseMiddleware 테스트."""

    async def test_inherits_trace_id(self, app):
        """헤더 trace-id 전달 시 동일 값이 request.state에 저장되는지 확인."""
        custom_trace_id = "custom-trace-12345"
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "trace 승계 테스트", "user_depts": ["test-dept"]},
                headers={"X-LF-Trace-ID": custom_trace_id},
            )
        assert response.status_code == 200
        assert response.json()["data"]["trace_id"] == custom_trace_id

    async def test_generates_trace_id(self, app):
        """헤더 없을 시 UUID 형식의 trace_id가 자동 생성되는지 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "trace 생성 테스트", "user_depts": ["test-dept"]},
            )
        assert response.status_code == 200
        trace_id = response.json()["data"]["trace_id"]
        # UUID 형식 검증
        uuid.UUID(trace_id)

    async def test_without_langfuse(self, app):
        """클라이언트 None이어도 trace_id 할당 + 요청 정상 처리 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "비활성화 테스트", "user_depts": ["test-dept"]},
            )
        assert response.status_code == 200
        assert "trace_id" in response.json()["data"]

    async def test_langfuse_error_does_not_break_request(self):
        """Langfuse trace 생성 예외 시에도 요청이 정상 처리되는지 확인."""
        from fastapi import FastAPI

        from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
        from app.adapters.mocks.mock_reranker import MockReranker
        from app.adapters.mocks.mock_vector_store import MockVectorStore
        from app.api.routes import router
        from app.services.search_service import SearchService

        mock_langfuse = MagicMock()
        mock_langfuse.start_as_current_observation.side_effect = Exception(
            "Langfuse 장애"
        )

        app_with_mock = FastAPI()
        app_with_mock.add_middleware(
            LangfuseMiddleware, langfuse_client=mock_langfuse
        )
        app_with_mock.state.search_service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )
        app_with_mock.include_router(router)

        transport = ASGITransport(app=app_with_mock)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "Langfuse 장애 테스트", "user_depts": ["test-dept"]},
            )
        assert response.status_code == 200
        assert "trace_id" in response.json()["data"]

    # === Story 4-2: trace-id 응답 헤더 + span 메타데이터 테스트 ===

    async def test_response_header_has_trace_id(self, app):
        """응답 헤더에 trace-id가 포함되는지 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "헤더 테스트", "user_depts": ["test-dept"]},
            )
        assert response.status_code == 200
        assert "X-LF-Trace-ID" in response.headers

    async def test_response_header_matches_request_trace_id(self, app):
        """요청 헤더의 trace-id가 응답 헤더에 동일하게 반환되는지 확인."""
        custom_trace_id = "custom-trace-12345"
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "헤더 매칭 테스트", "user_depts": ["test-dept"]},
                headers={"X-LF-Trace-ID": custom_trace_id},
            )
        assert response.status_code == 200
        assert response.headers["X-LF-Trace-ID"] == custom_trace_id

    async def test_response_header_generated_trace_id(self, app):
        """요청 헤더 없을 시 응답 헤더와 바디의 trace-id가 일치하는지 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "생성 trace-id 테스트", "user_depts": ["test-dept"]},
            )
        assert response.status_code == 200
        header_trace_id = response.headers["X-LF-Trace-ID"]
        body_trace_id = response.json()["data"]["trace_id"]
        assert len(header_trace_id) == 32  # uuid.uuid4().hex
        assert header_trace_id == body_trace_id

    async def test_empty_trace_id_header_generates_new(self, app):
        """빈 trace-id 헤더 전달 시 서버에서 새로 생성하는지 확인."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "빈 헤더 테스트", "user_depts": ["test-dept"]},
                headers={"X-LF-Trace-ID": ""},
            )
        assert response.status_code == 200
        header_trace_id = response.headers["X-LF-Trace-ID"]
        assert len(header_trace_id) == 32
        assert header_trace_id == response.json()["data"]["trace_id"]

    async def test_health_endpoint_skips_trace_id_header(self, app):
        """/health 응답에는 trace-id 헤더가 포함되지 않는다 (로그·트레이싱 제외)."""
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert "X-LF-Trace-ID" not in response.headers

    async def test_langfuse_span_output_recorded(self):
        """Langfuse span에 output 메타데이터가 기록되는지 확인."""
        from fastapi import FastAPI

        from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
        from app.adapters.mocks.mock_reranker import MockReranker
        from app.adapters.mocks.mock_vector_store import MockVectorStore
        from app.api.routes import router
        from app.services.search_service import SearchService

        mock_span = MagicMock()
        mock_langfuse = MagicMock()
        mock_langfuse.start_as_current_observation.return_value.__enter__.return_value = (
            mock_span
        )

        app_with_mock = FastAPI()
        app_with_mock.add_middleware(
            LangfuseMiddleware, langfuse_client=mock_langfuse
        )
        app_with_mock.state.search_service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )
        app_with_mock.include_router(router)

        transport = ASGITransport(app=app_with_mock)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "span output 테스트", "user_depts": ["test-dept"]},
                headers={"X-LF-Trace-ID": "test-span-output"},
            )
        assert response.status_code == 200
        mock_span.update.assert_called_once_with(
            output={"status_code": 200}
        )

    async def test_langfuse_span_stored_in_request_state(self):
        """request.state.langfuse_span에 span 객체가 저장되는지 확인."""
        from fastapi import FastAPI, Request

        mock_span = MagicMock()
        mock_langfuse = MagicMock()
        mock_langfuse.start_as_current_observation.return_value.__enter__.return_value = (
            mock_span
        )

        captured = {}

        app_with_mock = FastAPI()
        app_with_mock.add_middleware(
            LangfuseMiddleware, langfuse_client=mock_langfuse
        )

        @app_with_mock.get("/test-state")
        async def _check_state(request: Request):
            captured["langfuse_span"] = request.state.langfuse_span
            return {"ok": True}

        transport = ASGITransport(app=app_with_mock)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            await client.get(
                "/test-state",
                headers={"X-LF-Trace-ID": "test-state-check"},
            )

        assert captured["langfuse_span"] is mock_span

    async def test_search_uses_middleware_trace_id(self, app):
        """SearchService가 미들웨어의 trace_id를 사용하는지 검증."""
        custom_trace_id = "middleware-trace-xyz"
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "미들웨어 trace_id 테스트", "user_depts": ["test-dept"]},
                headers={"X-LF-Trace-ID": custom_trace_id},
            )
        assert response.status_code == 200
        assert response.json()["data"]["trace_id"] == custom_trace_id

    async def test_parent_observation_id_passed_to_langfuse(self):
        """X-LF-Parent-Id 헤더가 trace_context에 parent_observation_id로 전달되는지 확인."""
        from fastapi import FastAPI

        from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
        from app.adapters.mocks.mock_reranker import MockReranker
        from app.adapters.mocks.mock_vector_store import MockVectorStore
        from app.api.routes import router
        from app.services.search_service import SearchService

        mock_span = MagicMock()
        mock_langfuse = MagicMock()
        mock_langfuse.start_as_current_observation.return_value.__enter__.return_value = (
            mock_span
        )

        app_with_mock = FastAPI()
        app_with_mock.add_middleware(
            LangfuseMiddleware, langfuse_client=mock_langfuse
        )
        app_with_mock.state.search_service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )
        app_with_mock.include_router(router)

        transport = ASGITransport(app=app_with_mock)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            await client.post(
                "/v1/search",
                json={"query": "parent id 테스트", "user_depts": ["test-dept"]},
                headers={
                    "X-LF-Trace-ID": "trace-abc",
                    "X-LF-Parent-Id": "obs-789",
                },
            )

        call_kwargs = mock_langfuse.start_as_current_observation.call_args.kwargs
        assert call_kwargs["trace_context"]["trace_id"] == "trace-abc"
        assert call_kwargs["trace_context"]["parent_span_id"] == "obs-789"

    async def test_no_parent_id_header_still_works(self):
        """X-LF-Parent-Id 없이 X-LF-Trace-ID만 있어도 정상 동작하는지 확인."""
        from fastapi import FastAPI

        from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
        from app.adapters.mocks.mock_reranker import MockReranker
        from app.adapters.mocks.mock_vector_store import MockVectorStore
        from app.api.routes import router
        from app.services.search_service import SearchService

        mock_span = MagicMock()
        mock_langfuse = MagicMock()
        mock_langfuse.start_as_current_observation.return_value.__enter__.return_value = (
            mock_span
        )

        app_with_mock = FastAPI()
        app_with_mock.add_middleware(
            LangfuseMiddleware, langfuse_client=mock_langfuse
        )
        app_with_mock.state.search_service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )
        app_with_mock.include_router(router)

        transport = ASGITransport(app=app_with_mock)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/search",
                json={"query": "trace만 테스트", "user_depts": ["test-dept"]},
                headers={"X-LF-Trace-ID": "trace-only"},
            )

        assert response.status_code == 200
        call_kwargs = mock_langfuse.start_as_current_observation.call_args.kwargs
        assert call_kwargs["trace_context"] == {"trace_id": "trace-only"}
        assert "parent_span_id" not in call_kwargs["trace_context"]


# === Story 4-3: observe() 헬퍼 + SearchService span 기록 테스트 ===


class TestObserve:
    """observe() 헬퍼 함수 테스트."""

    def test_returns_nullcontext_when_disabled(self, monkeypatch):
        """Langfuse 비활성화 시 nullcontext를 반환하는지 확인."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "false")
        get_settings.cache_clear()
        _reset_langfuse_client()
        from app.core.monitoring import observe

        cm = observe(name="test")
        with cm as span:
            assert span is None

    def test_returns_context_manager_when_enabled(self):
        """Langfuse 활성화 시 start_as_current_observation을 반환하는지 확인."""
        import app.core.monitoring as mod
        from app.core.monitoring import observe

        mock_span = MagicMock()
        mock_client = MagicMock()
        mock_client.start_as_current_observation.return_value.__enter__ = (
            MagicMock(return_value=mock_span)
        )
        mock_client.start_as_current_observation.return_value.__exit__ = (
            MagicMock(return_value=False)
        )
        mod._langfuse_client = mock_client

        with observe(name="test-span", as_type="embedding", input={"k": "v"}) as span:
            assert span is mock_span

        mock_client.start_as_current_observation.assert_called_once_with(
            as_type="embedding", name="test-span", input={"k": "v"}
        )

    def test_returns_nullcontext_on_failure(self):
        """start_as_current_observation 실패 시 nullcontext를 반환하는지 확인."""
        import app.core.monitoring as mod
        from app.core.monitoring import observe

        mock_client = MagicMock()
        mock_client.start_as_current_observation.side_effect = Exception("실패")
        mod._langfuse_client = mock_client

        cm = observe(name="test")
        with cm as span:
            assert span is None


class TestSafeUpdateSpan:
    """safe_update_span() 함수 테스트."""

    def test_updates_span(self):
        """정상 span에 update가 호출되는지 확인."""
        from app.core.monitoring import safe_update_span

        mock_span = MagicMock()
        safe_update_span(mock_span, output={"key": "value"})
        mock_span.update.assert_called_once_with(output={"key": "value"})

    def test_skips_none_span(self):
        """span이 None이면 에러 없이 스킵하는지 확인."""
        from app.core.monitoring import safe_update_span

        safe_update_span(None, output={"key": "value"})  # 예외 없음

    def test_catches_update_exception(self):
        """span.update() 예외 시 에러 없이 흡수하는지 확인."""
        from app.core.monitoring import safe_update_span

        mock_span = MagicMock()
        mock_span.update.side_effect = Exception("직렬화 오류")
        safe_update_span(mock_span, output={"key": "value"})  # 예외 없음


class TestSearchServiceSpanRecording:
    """SearchService 파이프라인 span 기록 테스트."""

    @pytest.fixture
    def mock_langfuse_spans(self):
        """Mock Langfuse 클라이언트를 설정하고 각 observation마다 별도 span을 생성한다."""
        import app.core.monitoring as mod

        spans = []

        def _create_cm(**kwargs):
            span = MagicMock()
            spans.append(span)
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=span)
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        mock_client = MagicMock()
        mock_client.start_as_current_observation.side_effect = _create_cm
        mod._langfuse_client = mock_client

        return mock_client, spans

    @pytest.fixture
    def service(self):
        """Mock 어댑터를 주입한 SearchService."""
        from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
        from app.adapters.mocks.mock_reranker import MockReranker
        from app.adapters.mocks.mock_vector_store import MockVectorStore
        from app.services.search_service import SearchService

        return SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )

    async def test_embedding_span_created(self, mock_langfuse_spans, service):
        """임베딩 단계가 as_type='embedding' child span으로 기록되는지 확인. (AC #1)"""
        mock_client, spans = mock_langfuse_spans

        await service.search(query="테스트", user_depts=["test-dept"], search_k=5, top_k=3, trace_id="t")

        calls = mock_client.start_as_current_observation.call_args_list
        assert calls[0].kwargs["as_type"] == "embedding"
        assert calls[0].kwargs["name"] == "embedding"
        assert calls[0].kwargs["input"] == {"query": "테스트"}
        actual_output = spans[0].update.call_args.kwargs["output"]
        assert actual_output["vector_dim"] == 1024

    async def test_vector_search_span_created(self, mock_langfuse_spans, service):
        """벡터 검색 단계가 as_type='retriever' child span으로 기록되는지 확인. (AC #2)"""
        mock_client, spans = mock_langfuse_spans

        await service.search(query="테스트", user_depts=["test-dept"], search_k=5, top_k=3, trace_id="t")

        calls = mock_client.start_as_current_observation.call_args_list
        assert calls[1].kwargs["as_type"] == "retriever"
        assert calls[1].kwargs["name"] == "vector-search"
        assert calls[1].kwargs["input"] == {
            "search_k": 5,
            "user_depts": ["test-dept"],
            "excluded_docs": [],
            "search_mode": "dense_only",
        }
        actual_output = spans[1].update.call_args.kwargs["output"]
        assert actual_output["result_count"] == 5
        assert "results" in actual_output

    async def test_reranking_span_created(self, mock_langfuse_spans, service):
        """리랭킹 단계가 as_type='span' child span으로 기록되는지 확인. (AC #3)"""
        mock_client, spans = mock_langfuse_spans

        await service.search(query="테스트", user_depts=["test-dept"], search_k=5, top_k=3, trace_id="t")

        calls = mock_client.start_as_current_observation.call_args_list
        assert calls[2].kwargs["as_type"] == "span"
        assert calls[2].kwargs["name"] == "reranking"
        assert calls[2].kwargs["input"] == {"candidate_count": 5, "top_k": 3}
        actual_output = spans[2].update.call_args.kwargs["output"]
        assert actual_output["result_count"] == 3
        assert "results" in actual_output

    async def test_three_spans_created(self, mock_langfuse_spans, service):
        """파이프라인에서 정확히 3개의 child span이 생성되는지 확인. (AC #5)"""
        mock_client, spans = mock_langfuse_spans

        await service.search(query="테스트", user_depts=["test-dept"], search_k=5, top_k=3, trace_id="t")

        assert mock_client.start_as_current_observation.call_count == 3
        assert len(spans) == 3

    async def test_reranking_fallback_span_error(self, mock_langfuse_spans):
        """Fallback 발생 시 리랭킹 span에 level='ERROR'가 기록되는지 확인. (AC #4)"""
        from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
        from app.adapters.mocks.mock_vector_store import MockVectorStore
        from app.core.exceptions import RerankerException
        from app.core.interfaces import RerankerInterface
        from app.services.search_service import SearchService

        class FailingReranker(RerankerInterface):
            async def rerank(self, query, texts, top_k):
                raise RerankerException(msg="리랭커 연결 실패")

        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=FailingReranker(),
        )
        mock_client, spans = mock_langfuse_spans

        result = await service.search(
            query="테스트", user_depts=["test-dept"], search_k=5, top_k=3, trace_id="t"
        )

        assert result["fallback"] is True
        reranking_span = spans[2]
        reranking_span.update.assert_called_once_with(
            output={"error": "리랭커 연결 실패", "fallback": True},
            level="ERROR",
            status_message="리랭커 연결 실패",
        )

    async def test_langfuse_disabled_search_works(self):
        """Langfuse 비활성화 시 span 스킵 + 검색 정상 동작 확인. (AC #7)"""
        from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
        from app.adapters.mocks.mock_reranker import MockReranker
        from app.adapters.mocks.mock_vector_store import MockVectorStore
        from app.services.search_service import SearchService

        # _langfuse_client is None by fixture
        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )

        result = await service.search(
            query="테스트", user_depts=["test-dept"], search_k=5, top_k=3, trace_id="t"
        )

        assert result["query"] == "테스트"
        assert len(result["results"]) == 3

    async def test_span_creation_failure_does_not_break_search(self):
        """observe() 실패 시 검색 정상 동작 확인. (AC #8)"""
        import app.core.monitoring as mod
        from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
        from app.adapters.mocks.mock_reranker import MockReranker
        from app.adapters.mocks.mock_vector_store import MockVectorStore
        from app.services.search_service import SearchService

        mock_client = MagicMock()
        mock_client.start_as_current_observation.side_effect = Exception("장애")
        mod._langfuse_client = mock_client

        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )

        result = await service.search(
            query="테스트", user_depts=["test-dept"], search_k=5, top_k=3, trace_id="t"
        )

        assert result["query"] == "테스트"
        assert len(result["results"]) == 3

    async def test_span_update_failure_does_not_break_search(self, mock_langfuse_spans):
        """span.update() 실패 시 검색 정상 동작 확인. (AC #8)"""
        from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
        from app.adapters.mocks.mock_reranker import MockReranker
        from app.adapters.mocks.mock_vector_store import MockVectorStore
        from app.services.search_service import SearchService

        mock_client, spans = mock_langfuse_spans
        # 모든 span의 update()가 예외를 던지도록 설정
        orig_create = mock_client.start_as_current_observation.side_effect

        def _create_failing_span(**kwargs):
            span = MagicMock()
            span.update.side_effect = Exception("update 실패")
            spans.append(span)
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=span)
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        mock_client.start_as_current_observation.side_effect = _create_failing_span

        service = SearchService(
            embedding=MockEmbeddingAdapter(),
            vector_store=MockVectorStore(),
            reranker=MockReranker(),
        )

        result = await service.search(
            query="테스트", user_depts=["test-dept"], search_k=5, top_k=3, trace_id="t"
        )

        assert result["query"] == "테스트"
        assert len(result["results"]) == 3
