"""리랭커 어댑터 테스트."""

import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.adapters.reranker_adapter import RerankerAdapter
from app.core.config import Settings
from app.core.exceptions import RerankerException
from app.core.interfaces import RerankerInterface


class TestRerankerAdapter:
    """RerankerAdapter 테스트."""

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

    def _make_response(self, *, status_code=200, json_data=None, url=None):
        """httpx.Response mock을 생성한다."""
        request = httpx.Request("POST", url or "http://test-server:8011/rerank")
        return httpx.Response(
            status_code=status_code,
            json=json_data,
            request=request,
        )

    def _make_rerank_response(self, items=None, *, use_list_format: bool = False):
        """표준 리랭커 응답을 생성한다.

        Args:
            items: 응답 아이템 리스트.
            use_list_format: True면 리스트 직접 반환 형식, False면 {"value": [...]} 형식.
        """
        if items is None:
            items = [
                {"index": 1, "text": "문서2", "score": 0.95},
                {"index": 0, "text": "문서1", "score": 0.42},
                {"index": 2, "text": "문서3", "score": 0.10},
            ]
        if use_list_format:
            return self._make_response(json_data=items)
        return self._make_response(json_data={
            "value": items,
            "Count": len(items),
        })

    # === 인터페이스 테스트 ===

    async def test_implements_interface(self):
        """RerankerInterface를 구현한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)
        assert isinstance(adapter, RerankerInterface)

    # === 성공 케이스 ===

    async def test_rerank_success(self):
        """성공 시 API 응답에서 리랭킹 결과를 추출하여 반환한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        response = self._make_rerank_response()

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            result = await adapter.rerank(
                query="테스트 쿼리", texts=["문서1", "문서2", "문서3"], top_k=3
            )

        assert len(result) == 3
        assert result[0]["score"] == 0.95
        assert result[0]["text"] == "문서2"
        assert result[0]["index"] == 1

    async def test_rerank_success_list_format(self):
        """리스트 직접 반환 형식 API 응답을 정상 처리한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        response = self._make_rerank_response(use_list_format=True)

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            result = await adapter.rerank(
                query="테스트 쿼리", texts=["문서1", "문서2", "문서3"], top_k=3
            )

        assert len(result) == 3
        assert result[0]["score"] == 0.95
        assert result[0]["text"] == "문서2"
        assert result[0]["index"] == 1

    async def test_rerank_result_structure(self):
        """각 결과에 index, score, text가 포함된다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        response = self._make_rerank_response()

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            result = await adapter.rerank(
                query="쿼리", texts=["문서1", "문서2", "문서3"], top_k=3
            )

        for item in result:
            assert "index" in item
            assert "score" in item
            assert "text" in item

    async def test_rerank_top_k_slicing(self):
        """top_k로 결과 수를 제한한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        items = [
            {"index": i, "text": f"문서{i}", "score": 1.0 - i * 0.1}
            for i in range(5)
        ]
        response = self._make_rerank_response(items=items)

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            result = await adapter.rerank(
                query="쿼리", texts=[f"문서{i}" for i in range(5)], top_k=2
            )

        assert len(result) == 2

    async def test_sends_correct_request_body(self):
        """요청 본문에 query, texts, return_text를 포함하여 전송한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        response = self._make_rerank_response()

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            mock_client = self._make_mock_client(post_return=response)
            cls.return_value = mock_client
            await adapter.rerank(
                query="검색 쿼리", texts=["문서1", "문서2", "문서3"], top_k=3
            )

        mock_client.post.assert_called_once_with(
            settings.RERANKER_URL,
            json={
                "query": "검색 쿼리",
                "texts": ["문서1", "문서2", "문서3"],
                "return_text": True,
            },
        )

    async def test_uses_configured_timeout(self):
        """Settings.HTTP_TIMEOUT 값이 httpx 클라이언트에 적용된다."""
        settings = self._make_settings(HTTP_TIMEOUT=10.0)
        adapter = RerankerAdapter(settings)

        response = self._make_rerank_response()

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            await adapter.rerank(
                query="쿼리", texts=["문서1"], top_k=1
            )

        cls.assert_called_once_with(timeout=10.0)

    async def test_empty_texts_returns_empty_list(self):
        """빈 텍스트 리스트 시 API 호출 없이 빈 리스트를 반환한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            result = await adapter.rerank(query="쿼리", texts=[], top_k=3)

        cls.assert_not_called()
        assert result == []

    async def test_empty_texts_logs_warning(self, caplog):
        """빈 텍스트 리스트 시 warning 로그가 기록된다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        with caplog.at_level(logging.WARNING, logger="app.adapters.reranker_adapter"):
            await adapter.rerank(query="쿼리", texts=[], top_k=3)

        assert "빈 텍스트 리스트" in caplog.text

    # === 에러 케이스 ===

    async def test_timeout_raises_reranker_exception(self):
        """타임아웃 발생 시 RerankerException을 raise한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(
                post_side_effect=httpx.TimeoutException("timeout"),
            )
            with pytest.raises(RerankerException, match="타임아웃"):
                await adapter.rerank(
                    query="쿼리", texts=["문서1"], top_k=1
                )

    async def test_connect_error_raises_reranker_exception(self):
        """연결 실패 시 RerankerException을 raise한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(
                post_side_effect=httpx.ConnectError("connection refused"),
            )
            with pytest.raises(RerankerException, match="연결 실패"):
                await adapter.rerank(
                    query="쿼리", texts=["문서1"], top_k=1
                )

    async def test_http_error_raises_reranker_exception(self):
        """HTTP 에러 응답 시 RerankerException을 raise한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        response = self._make_response(status_code=500)

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            with pytest.raises(RerankerException, match="HTTP 에러"):
                await adapter.rerank(
                    query="쿼리", texts=["문서1"], top_k=1
                )

    async def test_missing_value_key_raises_reranker_exception(self):
        """응답에 value 키가 없으면 RerankerException을 raise한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        response = self._make_response(json_data={"Count": 0})

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            with pytest.raises(RerankerException, match="파싱 실패"):
                await adapter.rerank(
                    query="쿼리", texts=["문서1"], top_k=1
                )

    async def test_malformed_item_raises_reranker_exception(self):
        """value 배열 아이템에 필요한 키가 없으면 RerankerException을 raise한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        response = self._make_response(json_data={
            "value": [{"index": 0, "score": 0.5}],
            "Count": 1,
        })

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            with pytest.raises(RerankerException, match="파싱 실패"):
                await adapter.rerank(
                    query="쿼리", texts=["문서1"], top_k=1
                )

    async def test_non_list_value_raises_reranker_exception(self):
        """value가 배열이 아닌 문자열이면 RerankerException을 raise한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        response = self._make_response(json_data={
            "value": "not a list",
            "Count": 0,
        })

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=response)
            with pytest.raises(RerankerException, match="파싱 실패"):
                await adapter.rerank(
                    query="쿼리", texts=["문서1"], top_k=1
                )

    async def test_invalid_response_raises_reranker_exception(self):
        """응답이 유효한 JSON이 아니면 RerankerException을 raise한다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        request = httpx.Request("POST", settings.RERANKER_URL)
        raw_response = httpx.Response(
            status_code=200,
            content=b"not json",
            request=request,
        )

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(post_return=raw_response)
            with pytest.raises(RerankerException, match="파싱 실패"):
                await adapter.rerank(
                    query="쿼리", texts=["문서1"], top_k=1
                )

    async def test_exception_has_correct_rag_code(self):
        """RerankerException의 RAG 코드가 RAG100050이다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
            cls.return_value = self._make_mock_client(
                post_side_effect=httpx.ConnectError("refused"),
            )
            with pytest.raises(RerankerException) as exc_info:
                await adapter.rerank(
                    query="쿼리", texts=["문서1"], top_k=1
                )

        assert exc_info.value.code.value == "RAG100050"
        assert exc_info.value.status_code == 502

    # === 로그 검증 ===

    async def test_timeout_logs_error(self, caplog):
        """타임아웃 시 에러 로그가 기록된다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        with caplog.at_level(logging.ERROR, logger="app.adapters.reranker_adapter"):
            with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
                cls.return_value = self._make_mock_client(
                    post_side_effect=httpx.TimeoutException("timeout"),
                )
                with pytest.raises(RerankerException):
                    await adapter.rerank(
                        query="쿼리", texts=["문서1"], top_k=1
                    )

        assert "타임아웃" in caplog.text

    async def test_connect_error_logs_error(self, caplog):
        """연결 실패 시 에러 로그가 기록된다."""
        settings = self._make_settings()
        adapter = RerankerAdapter(settings)

        with caplog.at_level(logging.ERROR, logger="app.adapters.reranker_adapter"):
            with patch("app.adapters.reranker_adapter.httpx.AsyncClient") as cls:
                cls.return_value = self._make_mock_client(
                    post_side_effect=httpx.ConnectError("refused"),
                )
                with pytest.raises(RerankerException):
                    await adapter.rerank(
                        query="쿼리", texts=["문서1"], top_k=1
                    )

        assert "연결 실패" in caplog.text
