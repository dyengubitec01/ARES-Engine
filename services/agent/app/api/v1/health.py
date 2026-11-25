"""
Health Check API Endpoints.

헬스체크 엔드포인트 (Story 1.7)
- GET /health: 기본 헬스체크
- GET /health?deep=true: LLM 서버 상태 포함
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.core.config import settings
from app.core.health import check_llm_server_health
from app.core.schemas.response import CommonResponse

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check(
    deep: bool = Query(False, description="Include LLM server status")
) -> dict:
    """
    Health check endpoint with standard response format.

    Args:
        deep: If True, includes LLM server connectivity check.

    Returns:
        CommonResponse with health status data.
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    health_data: dict[str, Any] = {
        "status": "ok",
        "version": settings.APP_VERSION,
        "timestamp": timestamp,
    }

    # Deep health check (AC 1.7.2)
    if deep:
        llm_servers = await check_llm_server_health()
        health_data["llm_servers"] = llm_servers

    return CommonResponse.success(data=health_data).model_dump()
