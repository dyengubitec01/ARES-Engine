"""/v1/graph-search 엔드포인트 통합 테스트."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.mocks.mock_graph_retriever import MockGraphRetriever
from app.api.responses import RAGCode
from app.api.routes import router
from app.core.exceptions import RAGBaseException


def make_client(results=None):
    app = FastAPI()
    app.state.graph_retriever = MockGraphRetriever(results=results)
    app.include_router(router)

    @app.exception_handler(RAGBaseException)
    async def _h(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=200, content={"code": exc.code, "msg": exc.msg})

    return TestClient(app)


def test_success():
    client = make_client()
    resp = client.post("/v1/graph-search", json={"query": "증평군 사업"})
    body = resp.json()
    assert body["code"] == RAGCode.SEARCH_SUCCESS.value
    assert body["data"]["results"][0]["rank"] == 1
    assert "trace_id" in body["data"]


def test_no_result():
    client = make_client(results=[])
    resp = client.post("/v1/graph-search", json={"query": "없는쿼리"})
    assert resp.json()["code"] == RAGCode.NO_RESULT.value


def test_blank_query_bad_request():
    client = make_client()
    resp = client.post("/v1/graph-search", json={"query": "   "})
    assert resp.json()["code"] == RAGCode.BAD_REQUEST.value


def test_excluded_docs_filter():
    results = [
        {"chunk_id": "c1", "content": "x", "metadata": {"doc_id": "d1", "_source": "graph"}, "score": 5, "hits": 1},
        {"chunk_id": "c2", "content": "y", "metadata": {"doc_id": "d2", "_source": "graph"}, "score": 4, "hits": 1},
    ]
    client = make_client(results=results)
    resp = client.post("/v1/graph-search", json={"query": "q", "excluded_docs": ["d1"]})
    body = resp.json()
    ids = [r["metadata"]["doc_id"] for r in body["data"]["results"]]
    assert ids == ["d2"]
