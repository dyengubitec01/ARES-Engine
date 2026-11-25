"""
Integration Test Configuration (Story 2.6 AC 2.6.9).

통합 테스트용 서버 Fixture 및 공통 설정.
테스트 서버는 포트 8001에서 실행되어 운영 서버(8000)와 분리.

pytest tests/integration -v -m integration 으로 실행.
"""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator

import httpx
import pytest

# 테스트 서버 설정
TEST_SERVER_PORT = 8001
TEST_SERVER_HOST = "127.0.0.1"
TEST_SERVER_URL = f"http://{TEST_SERVER_HOST}:{TEST_SERVER_PORT}"
SERVER_STARTUP_TIMEOUT = 30  # seconds


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((TEST_SERVER_HOST, port)) == 0


def wait_for_server(url: str, timeout: float = SERVER_STARTUP_TIMEOUT) -> bool:
    """Wait for server to be ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"{url}/health", timeout=2.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def server_url() -> Generator[str, None, None]:
    """
    테스트 서버 URL 제공.

    - 이미 실행 중이면 기존 서버 사용
    - 아니면 subprocess로 새 서버 시작
    - 테스트 종료 후 자동 정리
    """
    # 이미 서버가 실행 중인지 확인
    if is_port_in_use(TEST_SERVER_PORT):
        print(f"\n[Integration Test] Using existing server at {TEST_SERVER_URL}")
        yield TEST_SERVER_URL
        return

    # 새 서버 시작
    print(f"\n[Integration Test] Starting test server on port {TEST_SERVER_PORT}...")

    env = os.environ.copy()
    env["MODEL_CONFIG_PATH"] = "config/models.test.yaml"
    env["PORT"] = str(TEST_SERVER_PORT)
    env["HOST"] = TEST_SERVER_HOST

    # uvicorn으로 서버 시작
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host", TEST_SERVER_HOST,
            "--port", str(TEST_SERVER_PORT),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.getcwd(),
    )

    try:
        # 서버 준비 대기
        if not wait_for_server(TEST_SERVER_URL):
            # 실패 시 출력 로그
            stdout, stderr = process.communicate(timeout=5)
            print(f"Server stdout: {stdout.decode()}")
            print(f"Server stderr: {stderr.decode()}")
            pytest.fail(f"Test server failed to start within {SERVER_STARTUP_TIMEOUT}s")

        print(f"[Integration Test] Server ready at {TEST_SERVER_URL}")
        yield TEST_SERVER_URL

    finally:
        # 서버 종료
        print("\n[Integration Test] Shutting down test server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        print("[Integration Test] Test server stopped")


@pytest.fixture
def http_client(server_url: str) -> Generator[httpx.Client, None, None]:
    """Synchronous HTTP client for testing."""
    with httpx.Client(base_url=server_url, timeout=60.0) as client:
        yield client


@pytest.fixture
def async_client(server_url: str) -> httpx.AsyncClient:
    """Async HTTP client for testing."""
    return httpx.AsyncClient(base_url=server_url, timeout=60.0)


def llm_available() -> bool:
    """Check if LLM server is available."""
    from app.core.config import settings

    try:
        headers = {}
        if settings.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
        resp = httpx.get(
            f"{settings.PRIMARY_LLM_BASE_URL}/models",
            headers=headers,
            timeout=2.0,
        )
        return resp.status_code == 200
    except Exception:
        return False


def langfuse_configured() -> bool:
    """Check if LangFuse is configured."""
    from app.core.config import settings

    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)


def rag_server_available() -> bool:
    """Check if RAG server is available."""
    from app.core.config import settings

    try:
        resp = httpx.get(f"{settings.RAG_BASE_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def tool_server_available() -> bool:
    """Check if Tool server is available."""
    from app.core.config import settings

    try:
        resp = httpx.get(f"{settings.TOOL_BASE_URL}/health", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


# Skip markers
skip_no_llm = pytest.mark.skipif(
    not llm_available(),
    reason="LLM server not available",
)

skip_no_langfuse = pytest.mark.skipif(
    not langfuse_configured(),
    reason="LangFuse not configured",
)

skip_no_rag = pytest.mark.skipif(
    not rag_server_available(),
    reason="RAG server not available",
)

skip_no_tool = pytest.mark.skipif(
    not tool_server_available(),
    reason="Tool server not available",
)
