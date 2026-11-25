"""Role-Based 모델 매핑 모듈.

코드에서 모델명 대신 역할(primary, fast, reasoning)로 호출한다.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# 프로젝트 루트 기준 config 디렉터리
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
MODELS_CONFIG_PATH = PROJECT_ROOT / "config" / "models.yaml"


@dataclass(frozen=True)
class ModelRole:
    """모델 역할 정보."""

    role: str
    model: str
    description: str
    fallback_role: str | None


@dataclass(frozen=True)
class ModelsConfig:
    """모델 설정 전체."""

    roles: dict[str, ModelRole]
    default_role: str
    fallback_message: str

    def get_role(self, role: str) -> ModelRole | None:
        """역할 정보 조회."""
        return self.roles.get(role)

    def get_model(self, role: str) -> str | None:
        """역할에 해당하는 모델명 조회."""
        role_info = self.get_role(role)
        return role_info.model if role_info else None

    def get_fallback_chain(self, role: str) -> list[str]:
        """역할의 fallback 체인 조회.

        Args:
            role: 시작 역할.

        Returns:
            fallback 체인 (시작 역할 포함). 예: ["primary", "fast"]
        """
        chain: list[str] = []
        visited: set[str] = set()
        current = role

        while current and current not in visited:
            if current in self.roles:
                chain.append(current)
                visited.add(current)
                current = self.roles[current].fallback_role
            else:
                break

        return chain


def _load_models_yaml() -> dict[str, Any]:
    """models.yaml 파일 로드.

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때.
    """
    if not MODELS_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"필수 설정 파일을 찾을 수 없습니다: {MODELS_CONFIG_PATH}"
        )

    with MODELS_CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
        logger.info("모델 설정 로드: %s", MODELS_CONFIG_PATH)
        return data if isinstance(data, dict) else {}


def _validate_no_circular_fallback(roles: dict[str, ModelRole]) -> None:
    """fallback 체인에 순환 참조가 없는지 검증.

    Args:
        roles: 역할 딕셔너리.

    Raises:
        ValueError: 순환 참조 발견 시.
    """
    for role_name in roles:
        visited: set[str] = set()
        current: str | None = role_name

        while current:
            if current in visited:
                raise ValueError(
                    f"순환 참조 감지: '{role_name}' fallback 체인에서 "
                    f"'{current}'이(가) 반복됩니다."
                )
            visited.add(current)
            role_info = roles.get(current)
            current = role_info.fallback_role if role_info else None


@lru_cache
def load_models_config() -> ModelsConfig:
    """모델 설정 로드.

    Returns:
        ModelsConfig 인스턴스.

    Raises:
        FileNotFoundError: models.yaml 파일이 없을 때.
        ValueError: 필수 필드 누락 또는 순환 참조 시.
    """
    data = _load_models_yaml()

    # 역할 파싱
    roles_data = data.get("roles", {})
    roles: dict[str, ModelRole] = {}

    for role_name, role_info in roles_data.items():
        if not isinstance(role_info, dict):
            continue

        # 필수 필드 검증
        model = role_info.get("model")
        if not model:
            raise ValueError(
                f"역할 '{role_name}'의 'model' 필드가 누락되었습니다."
            )

        roles[role_name] = ModelRole(
            role=role_name,
            model=model,
            description=role_info.get("description", ""),
            fallback_role=role_info.get("fallback_role"),
        )

    # 순환 참조 검증
    _validate_no_circular_fallback(roles)

    return ModelsConfig(
        roles=roles,
        default_role=data.get("default_role", "primary"),
        fallback_message=data.get(
            "fallback_message",
            "현재 AI 서비스를 이용할 수 없습니다.",
        ),
    )


def get_model_for_role(role: str | None = None) -> str:
    """역할에 해당하는 모델명 반환.

    Args:
        role: 역할명. None이면 default_role 사용.

    Returns:
        모델명. 역할이 없으면 빈 문자열.
    """
    config = load_models_config()
    target_role = role or config.default_role
    return config.get_model(target_role) or ""


def get_fallback_chain(role: str | None = None) -> list[str]:
    """역할의 fallback 체인 반환.

    Args:
        role: 역할명. None이면 default_role 사용.

    Returns:
        fallback 체인 리스트.
    """
    config = load_models_config()
    target_role = role or config.default_role
    return config.get_fallback_chain(target_role)
