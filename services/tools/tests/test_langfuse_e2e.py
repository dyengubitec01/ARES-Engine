"""Langfuse 실환경 E2E 검증 테스트.

.env 파일 또는 환경변수에 LANGFUSE_PUBLIC_KEY가 설정된 경우 실행된다.
CI에서 Langfuse 환경변수 없이 실행 시 자동 스킵.

실행 방법:
    pytest tests/test_langfuse_e2e.py -v
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드 (이미 설정된 값은 덮어쓰지 않음)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

pytestmark = pytest.mark.skipif(
    not os.getenv("LANGFUSE_PUBLIC_KEY"),
    reason="Langfuse 환경변수 미설정 — E2E 테스트 스킵",
)


@pytest.fixture(autouse=True)
def _clear_langfuse_cache():
    """테스트 간 Langfuse 클라이언트 캐시 초기화."""
    from src.middleware.langfuse import get_langfuse_client

    get_langfuse_client.cache_clear()
    yield
    get_langfuse_client.cache_clear()


class TestLangfuseE2EConnection:
    """Langfuse 실환경 연결 E2E 테스트."""

    def test_client_initializes_with_real_credentials(self):
        """실제 환경변수로 Langfuse 클라이언트가 정상 초기화되는지 확인."""
        from src.middleware.langfuse import get_langfuse_client

        client = get_langfuse_client()
        assert client is not None

    def test_create_span_without_trace_context_returns_none(self):
        """trace_context 없이 create_span() 호출 시 None 반환 (독립 observation 방지)."""
        from src.middleware.langfuse import create_span

        result = create_span(
            "e2e-test-create-span",
            input_data={"test": True},
            metadata={"source": "test_langfuse_e2e.py"},
        )
        assert result is None, (
            "trace_context 없이 create_span()은 None을 반환해야 한다."
        )
