"""API 라우터 - 검색 엔드포인트."""

import uuid
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.responses import no_result_response, success_response
from app.core.config import get_settings
from app.core.exceptions import BadRequestException

router = APIRouter(prefix="/v1", tags=["search"])


class SearchRequest(BaseModel):
    """검색 요청 모델."""

    query: str
    user_depts: list[str]
    excluded_docs: list[str] = []
    top_k: Optional[int] = None
    search_k: Optional[int] = None


@router.post("/search")
async def search(body: SearchRequest, request: Request) -> dict:
    """검색 엔드포인트.

    query를 받아 벡터 검색 → 리랭킹 파이프라인을 수행하고
    표준 응답 규격으로 결과를 반환한다.
    """
    settings = get_settings()
    search_service = request.app.state.search_service

    # 입력 검증
    if not body.query.strip():
        raise BadRequestException(msg="잘못된 요청: query는 빈 문자열일 수 없습니다")

    if not body.user_depts:
        raise BadRequestException(msg="잘못된 요청: user_depts는 빈 리스트일 수 없습니다")

    top_k = body.top_k if body.top_k is not None else settings.TOP_K
    search_k = body.search_k if body.search_k is not None else settings.SEARCH_K

    if top_k <= 0 or search_k <= 0:
        raise BadRequestException(msg="잘못된 요청: top_k와 search_k는 양수여야 합니다")

    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    root_span = getattr(request.state, "langfuse_span", None)
    parent_observation_id = getattr(root_span, "id", None)

    data = await search_service.search(
        query=body.query,
        user_depts=body.user_depts,
        excluded_docs=body.excluded_docs,
        search_k=search_k,
        top_k=top_k,
        trace_id=trace_id,
        score_threshold=settings.SCORE_THRESHOLD,
        parent_observation_id=parent_observation_id,
    )

    if not data["results"]:
        return no_result_response()

    return success_response(data=data)
