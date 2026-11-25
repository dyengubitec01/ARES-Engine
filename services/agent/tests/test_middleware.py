"""Tests for Story 3.2: middleware.py (AC 3.2.2, AC 3.2.3)."""

import json
import logging

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.logging_config import configure_logging
from app.core.middleware import LoggingMiddleware


@pytest.fixture(autouse=True)
def _setup_logging():
    """Reset and configure logging for each test."""
    root = logging.getLogger()
    root.handlers.clear()
    structlog.reset_defaults()
    configure_logging(json_format=False, log_level="DEBUG")
    yield
    root.handlers.clear()


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app with LoggingMiddleware."""
    app = FastAPI()
    app.add_middleware(LoggingMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/v1/models")
    async def models():
        return {"models": []}

    @app.post("/v1/chat")
    async def chat():
        # request_id가 contextvars에 바인딩되어 있는지 확인
        ctx = structlog.contextvars.get_contextvars()
        return {"request_id": ctx.get("request_id", "")}

    @app.get("/error")
    async def error():
        raise RuntimeError("test error")

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    def test_request_id_generated(self, client: TestClient) -> None:
        """AC 3.2.2: 요청마다 UUID v4 request_id가 생성된다."""
        response = client.post("/v1/chat")
        assert response.status_code == 200

        data = response.json()
        request_id = data["request_id"]
        assert request_id  # 비어있지 않음
        assert len(request_id) == 36  # UUID v4 format: 8-4-4-4-12

    def test_unique_request_ids(self, client: TestClient) -> None:
        """AC 3.2.2: 각 요청마다 다른 request_id가 생성된다."""
        resp1 = client.post("/v1/chat")
        resp2 = client.post("/v1/chat")

        id1 = resp1.json()["request_id"]
        id2 = resp2.json()["request_id"]
        assert id1 != id2

    def test_access_log_emitted(self, client: TestClient, caplog) -> None:
        """AC 3.2.2: 요청 완료 후 Access Log가 기록된다."""
        import logging as _logging

        with caplog.at_level(_logging.INFO, logger="access"):
            response = client.get("/v1/models")
            assert response.status_code == 200

        assert any("request_completed" in str(r.message) for r in caplog.records)

    def test_access_log_contains_fields(self, client: TestClient, tmp_path) -> None:
        """AC 3.2.2: Access Log에 method, path, status_code, duration_ms, client_ip가 포함된다."""
        # JSON 모드로 재설정하여 파싱 가능하게
        root = logging.getLogger()
        root.handlers.clear()
        structlog.reset_defaults()
        configure_logging(
            json_format=True,
            log_level="DEBUG",
            app_name="test",
            log_dir=str(tmp_path),
        )

        response = client.get("/v1/models")
        assert response.status_code == 200

        # 파일에서 Access Log 확인
        log_files = list(tmp_path.glob("*.log"))
        assert len(log_files) == 1

        content = log_files[0].read_text(encoding="utf-8").strip()
        access_lines = [
            json.loads(line) for line in content.split("\n")
            if "request_completed" in line
        ]
        assert len(access_lines) >= 1

        log_entry = access_lines[0]
        assert log_entry["event"] == "request_completed"
        assert log_entry["method"] == "GET"
        assert log_entry["path"] == "/v1/models"
        assert log_entry["status_code"] == 200
        assert "duration_ms" in log_entry
        assert "client_ip" in log_entry
        assert "request_id" in log_entry

    def test_access_log_on_exception(self, client: TestClient, caplog) -> None:
        """AC 3.2.2: 요청 중 예외 발생 시 request_failed Access Log가 기록된다."""
        import logging as _logging

        with caplog.at_level(_logging.ERROR, logger="access"):
            with pytest.raises(Exception):
                client.get("/error")

        assert any("request_failed" in str(r.message) for r in caplog.records)
