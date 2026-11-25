"""
Health Check Service.

헬스체크 로직 (Story 1.7 리팩토링)
LLM 서버 연결 상태 및 지연시간 측정.
"""

import time
from typing import Any

import httpx

from app.core.config import settings


async def check_llm_server_health() -> dict[str, dict[str, Any]]:
    """
    Check LLM server connectivity and measure latency.

    Returns:
        Dict with server status and latency for each configured server.
    """
    result: dict[str, dict[str, Any]] = {}
    servers = {
        "primary": settings.PRIMARY_LLM_BASE_URL,
        "fallback": settings.SECONDARY_LLM_BASE_URL,
    }

    async with httpx.AsyncClient(timeout=settings.HEALTH_CHECK_TIMEOUT) as client:
        for name, url in servers.items():
            try:
                start = time.perf_counter()
                response = await client.get(f"{url}/models")
                latency_ms = int((time.perf_counter() - start) * 1000)

                if response.status_code == 200:
                    result[name] = {"status": "connected", "latency_ms": latency_ms}
                else:
                    result[name] = {"status": "disconnected", "latency_ms": None}
            except (httpx.ConnectError, httpx.TimeoutException):
                result[name] = {"status": "disconnected", "latency_ms": None}

    return result
