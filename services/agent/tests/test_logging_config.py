"""Tests for Story 3.2: logging_config.py (AC 3.2.1, AC 3.2.6, AC 3.2.7)."""

import json
import logging

import structlog

from app.core.logging_config import configure_logging


class TestConfigureLogging:
    """Tests for configure_logging()."""

    def setup_method(self) -> None:
        """Reset logging state before each test."""
        root = logging.getLogger()
        root.handlers.clear()
        # Reset structlog configuration
        structlog.reset_defaults()

    def test_console_renderer_in_dev_mode(self) -> None:
        """AC 3.2.1/3.2.6: LOG_JSON_FORMAT=false → ConsoleRenderer (개발)."""
        configure_logging(json_format=False, log_level="DEBUG")

        root = logging.getLogger()
        assert root.level == logging.DEBUG
        # stdout 핸들러만 존재 (파일 없음)
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.StreamHandler)

    def test_json_renderer_in_prod_mode(self, tmp_path) -> None:
        """AC 3.2.1/3.2.6: LOG_JSON_FORMAT=true → JSONRenderer (운영) + 파일 핸들러."""
        configure_logging(
            json_format=True,
            log_level="INFO",
            app_name="test-agent",
            log_dir=str(tmp_path),
            retention_days=7,
        )

        root = logging.getLogger()
        assert root.level == logging.INFO
        # stdout + 파일 핸들러 2개
        assert len(root.handlers) == 2

    def test_json_format_output(self, tmp_path) -> None:
        """AC 3.2.1: JSON 포맷으로 출력 시 파싱 가능한 JSON인지 확인."""
        configure_logging(
            json_format=True,
            log_level="INFO",
            app_name="test-agent",
            log_dir=str(tmp_path),
            retention_days=7,
        )

        log = structlog.get_logger("test.module")
        log.info("test_event", key="value")

        # 파일에 기록된 내용 확인
        log_files = list(tmp_path.glob("*.log"))
        assert len(log_files) == 1

        content = log_files[0].read_text(encoding="utf-8").strip()
        lines = content.split("\n")
        assert len(lines) >= 1

        # JSON 파싱 가능 확인
        parsed = json.loads(lines[-1])
        assert parsed["event"] == "test_event"
        assert parsed["key"] == "value"
        assert "timestamp" in parsed
        assert "+09:00" in parsed["timestamp"]  # KST
        assert parsed["level"] == "info"

    def test_noisy_loggers_suppressed(self) -> None:
        """AC 3.2.1: 서드파티 로거 레벨 WARNING으로 조정."""
        configure_logging(json_format=False, log_level="DEBUG")

        for name in ("httpcore", "httpx", "uvicorn.access"):
            assert logging.getLogger(name).level == logging.WARNING

    def test_file_handler_rotation_config(self, tmp_path) -> None:
        """AC 3.2.7: TimedRotatingFileHandler 설정 확인."""
        configure_logging(
            json_format=True,
            log_level="INFO",
            app_name="agent",
            log_dir=str(tmp_path),
            retention_days=14,
        )

        root = logging.getLogger()
        file_handler = root.handlers[1]  # 두 번째가 파일 핸들러
        assert hasattr(file_handler, "when")
        assert file_handler.when.upper() == "MIDNIGHT"
        assert file_handler.backupCount == 14
        assert file_handler.encoding == "utf-8"
