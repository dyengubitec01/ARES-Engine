"""pytest 공통 설정 — 통합 테스트 마커 제어, 테스트용 앱 fixture."""

import pytest

from app.adapters.mocks.mock_embedding import MockEmbeddingAdapter
from app.adapters.mocks.mock_reranker import MockReranker
from app.adapters.mocks.mock_vector_store import MockVectorStore
from app.main import create_app
from app.services.search_service import SearchService


@pytest.fixture
def app():
    """테스트용 FastAPI 앱 — Mock 어댑터 주입."""
    test_app = create_app()
    test_app.state.search_service = SearchService(
        embedding=MockEmbeddingAdapter(),
        vector_store=MockVectorStore(),
        reranker=MockReranker(),
    )
    return test_app


def pytest_addoption(parser):
    """--run-integration 커맨드라인 옵션 등록."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="통합 테스트 실행 (실서버 연동 필요)",
    )


def pytest_collection_modifyitems(config, items):
    """--run-integration 미지정 시 integration 마커 테스트를 자동 skip."""
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(reason="--run-integration 옵션 필요")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
