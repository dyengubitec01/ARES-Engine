"""요약 엔드포인트 라우터.

POST /v1/summary — 대화 이력 기반 요약 API.
"""

from fastapi import APIRouter, Depends, Header, Request

from src.providers.base import BaseLLMProvider
from src.providers.deps import get_llm_provider
from src.schemas.codes import TOLCode
from src.schemas.response import TOLResponse
from src.schemas.summary import SummaryData, SummaryRequest
from src.services.summary import summarize

router = APIRouter(tags=["summary"])


@router.post(
    "/v1/summary",
    response_model=TOLResponse[SummaryData],
    responses={
        503: {
            "description": "LLM 프로바이더 응답 실패",
            "content": {
                "application/json": {
                    "example": {
                        "code": "TOL020130",
                        "msg": "LLM 프로바이더 응답 실패",
                    }
                }
            },
        },
        400: {
            "description": "유효하지 않은 Scope",
            "content": {
                "application/json": {
                    "example": {
                        "code": "TOL010130",
                        "msg": "유효하지 않은 Scope입니다",
                    }
                }
            },
        },
        422: {
            "description": "입력 검증 실패 (history 누락, 빈 배열, role/content 빈 문자열 등)",
        },
        500: {
            "description": "서버 내부 오류",
            "content": {
                "application/json": {
                    "example": {
                        "code": "TOL000030",
                        "msg": "서버 내부 오류",
                    }
                }
            },
        },
    },
)
async def summary_endpoint(
    body: SummaryRequest,
    raw_request: Request,
    x_tol_scope: str | None = Header(
        default=None,
        alias="X-TOL-Scope",
        description="호출자 Scope (ScopeMiddleware에서 자동 검증)",
    ),
    provider: BaseLLMProvider = Depends(get_llm_provider),
) -> TOLResponse[SummaryData]:
    """대화 이력 기반 요약 엔드포인트.

    Scope 검증은 ScopeMiddleware에서 자동 수행된다.
    target_n_tokens는 config/prompts.yaml에서 관리.

    Args:
        body: 요약 요청 (history + summary).
        raw_request: FastAPI Request (langfuse_span 추출용).
        x_tol_scope: X-TOL-Scope 헤더 (Swagger 문서용, 검증은 미들웨어).
        provider: LLM Provider (DI 주입).

    Returns:
        TOL 표준 응답 (TOL020100 + 요약 결과).
    """
    # 미들웨어가 저장한 trace_context 추출 (SDK 내부 속성 접근 없이 전파)
    trace_context: dict[str, str] | None = getattr(
        raw_request.state, "trace_context", None
    )

    result = await summarize(
        body.history,
        provider,
        summary=body.summary,
        trace_context=trace_context,
    )
    return TOLResponse.success(
        code=TOLCode.SUCCESS_SUMMARY,
        data=SummaryData(summary=result),
    )
