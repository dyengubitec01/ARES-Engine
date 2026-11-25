"""
서비스 공통 로그 설정 (ADR-004).

역할:
1. structlog 프로세서 파이프라인 구성
2. JSON (운영) / 컬러 텍스트 (개발) 렌더러 선택
3. TimedRotatingFileHandler로 일일 로테이션 + 보관 기간 관리
4. 기존 stdlib logger도 structlog 포맷터를 통해 JSON 출력
5. 서드파티 로거 (httpcore, httpx, uvicorn.access) 레벨 WARNING으로 조정

호출:
    main.py의 앱 시작 시 configure_logging() 1회 호출
"""

import logging
import logging.handlers
import os
import time as _time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog

KST = ZoneInfo("Asia/Seoul")

# 서드파티 로거 중 레벨을 WARNING으로 조정할 대상
_NOISY_LOGGERS = (
    "httpcore",
    "httpx",
    "uvicorn.access",
)


def _kst_timestamper(logger: logging.Logger, method_name: str, event_dict: dict) -> dict:
    """KST 타임존 ISO 8601 타임스탬프를 추가한다."""
    now = datetime.now(tz=KST)
    event_dict["timestamp"] = now.isoformat(timespec="milliseconds")
    return event_dict


def _make_file_handler(
    app_name: str,
    log_dir: str,
    retention_days: int,
) -> logging.Handler:
    """TimedRotatingFileHandler를 생성한다.

    파일명 패턴: {app_name}.log → 로테이션 시 {app_name}.log.YYYY-MM-DD
    커스텀 namer로 {app_name}.YYYY-MM-DD.log 형태로 변환.
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    log_file = log_path / f"{app_name}.log"
    handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
        atTime=None,
    )
    # 커스텀 namer: app.log.2026-03-04 → app.2026-03-04.log
    handler.namer = lambda name: name.replace(f"{app_name}.log.", f"{app_name}.") + ".log"

    return handler


def configure_logging(
    *,
    json_format: bool = False,
    log_level: str = "INFO",
    app_name: str = "agent",
    log_dir: str = "/app/logs",
    retention_days: int = 14,
) -> None:
    """structlog + stdlib 통합 로그를 설정한다.

    Args:
        json_format: True → JSONRenderer (운영), False → ConsoleRenderer (개발)
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
        app_name: 서비스 이름 (파일명에 사용)
        log_dir: 로그 파일 디렉토리 (json_format=True 일 때만 사용)
        retention_days: 로그 보관 일수
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # ── structlog 공통 프로세서 ──
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        _kst_timestamper,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        # 운영: JSON
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer(
            ensure_ascii=False
        )
    else:
        # 개발: 컬러 텍스트
        renderer = structlog.dev.ConsoleRenderer()

    # ── structlog 설정 ──
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ── stdlib ProcessorFormatter (structlog → stdlib 통합) ──
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    # ── 핸들러 구성 ──
    handlers: list[logging.Handler] = []

    # stdout 핸들러 (항상 사용)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    handlers.append(stream_handler)

    # 파일 핸들러 (운영 환경만)
    if json_format:
        file_handler = _make_file_handler(app_name, log_dir, retention_days)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # ── root logger 설정 ──
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    for handler in handlers:
        root_logger.addHandler(handler)

    # ── 서드파티 로거 레벨 조정 ──
    for noisy in _NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # ── OS 타임존 (TimedRotatingFileHandler midnight 기준) ──
    os.environ.setdefault("TZ", "Asia/Seoul")
    if hasattr(_time, "tzset"):
        _time.tzset()  # Linux/Docker에서 TZ 변경을 time 모듈에 반영
