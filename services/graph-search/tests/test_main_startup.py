"""create_app DI 배선 테스트."""

from app.core.interfaces import GraphRetrieverInterface
from app.main import create_app


def test_app_wires_graph_retriever():
    app = create_app()
    retriever = app.state.graph_retriever
    assert isinstance(retriever, GraphRetrieverInterface)


def test_routes_registered():
    app = create_app()
    paths = set(app.openapi()["paths"].keys())
    assert "/v1/graph-search" in paths
    assert "/health" in paths
