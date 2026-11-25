"""
Model List API Endpoints.

모델 목록 엔드포인트 (Story 1.7)
- GET /v1/models: 사용 가능한 모델 및 역할 목록
"""

from fastapi import APIRouter

from app.core.config import get_model_config
from app.core.schemas.response import CommonResponse

router = APIRouter(prefix="/v1", tags=["Models"])


@router.get("/models")
async def list_models() -> dict:
    """
    List available models and their roles.

    Returns:
        CommonResponse with list of roles and their models.
    """
    model_config = get_model_config()

    roles_list = []
    for role_name, role_config in model_config.roles.items():
        roles_list.append({
            "role": role_name,
            "model": role_config.model,
            "server": role_config.server,
        })

    return CommonResponse.success(data={"roles": roles_list}).model_dump()
