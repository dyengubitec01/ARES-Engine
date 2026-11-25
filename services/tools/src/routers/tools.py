"""도구 목록 엔드포인트 라우터.

GET /tools — Scope 기반 도구 목록 API.
"""

from fastapi import APIRouter, Header

from src.schemas.codes import TOLCode
from src.schemas.response import TOLResponse
from src.schemas.tools import ToolDefinition, ToolFunction, ToolsData
from src.services.scoping import get_tools_for_scope

router = APIRouter(tags=["tools"])


@router.get(
    "/v1/tools",
    response_model=TOLResponse[ToolsData],
    responses={
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
async def tools_endpoint(
    x_tol_scope: str | None = Header(default=None, alias="X-TOL-Scope"),
) -> TOLResponse[ToolsData]:
    """Scope 기반 도구 목록 엔드포인트.

    X-TOL-Scope 헤더에 따라 필터링된 도구 목록을 반환한다.
    헤더 미전달 시 400 에러.

    Args:
        x_tol_scope: X-TOL-Scope 헤더 값.

    Returns:
        TOL 표준 응답 (TOL010100 + 도구 목록).
    """
    filtered = get_tools_for_scope(x_tol_scope)

    tools = [
        ToolDefinition(
            function=ToolFunction(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
            ),
        )
        for t in filtered
    ]

    return TOLResponse.success(
        code=TOLCode.SUCCESS_QUERY,
        data=ToolsData(tools=tools),
    )
