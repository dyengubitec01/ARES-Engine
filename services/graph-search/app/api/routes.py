"""API 라우터 - 그래프 검색 엔드포인트."""

import uuid
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.responses import no_result_response, success_response
from app.core.exceptions import BadRequestException

router = APIRouter(prefix="/v1", tags=["graph-search"])


class GraphSearchRequest(BaseModel):
    query: str
    excluded_docs: list[str] = []
    chunk_limit: Optional[int] = None
    # 부서 ACL: 지금은 수신만 하고 필터는 하지 않는다 (벡터 축과 대칭 유지).
    # 향후 부서 필터가 필요해지면 doc_document_content.auth_dept_id 기준으로
    # 이 값을 rank_chunks 쿼리에 바로 걸 수 있도록 계약만 미리 뚫어둔다.
    user_depts: list[str] = []


@router.post("/graph-search")
async def graph_search(body: GraphSearchRequest, request: Request) -> dict:
    if not body.query.strip():
        raise BadRequestException(msg="잘못된 요청: query는 빈 문자열일 수 없습니다")

    graph_retriever = request.app.state.graph_retriever
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))

    # Langfuse: root span(미들웨어 생성) 밑으로 3-Step child span을 nest하기 위한 컨텍스트
    root_span = getattr(request.state, "langfuse_span", None)
    parent_observation_id = getattr(root_span, "id", None)
    trace_context = None
    if trace_id and parent_observation_id:
        trace_context = {"trace_id": trace_id, "parent_span_id": parent_observation_id}

    results = await graph_retriever.retrieve(body.query, trace_context=trace_context)

    if body.excluded_docs:
        excluded = set(body.excluded_docs)
        results = [
            r for r in results
            if r["metadata"].get("doc_id") not in excluded
        ]

    if not results:
        return no_result_response()

    # rank 부여
    for rank, r in enumerate(results, start=1):
        r["rank"] = rank

    return success_response(data={
        "query": body.query,
        "trace_id": trace_id,
        "results": results,
    })
