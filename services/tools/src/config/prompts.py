"""프롬프트 템플릿 설정 모듈.

config/prompts.yaml에서 프롬프트 템플릿과 파라미터를 로드한다.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
PROMPTS_CONFIG_PATH = PROJECT_ROOT / "config" / "prompts.yaml"


@dataclass(frozen=True)
class PromptTemplate:
    """프롬프트 템플릿 정보."""

    name: str
    system: str
    variables: dict[str, Any]


@dataclass(frozen=True)
class PromptsConfig:
    """프롬프트 설정 전체."""

    templates: dict[str, PromptTemplate]

    def get_template(self, name: str) -> PromptTemplate | None:
        """템플릿 이름으로 조회."""
        return self.templates.get(name)


def _load_prompts_yaml() -> dict[str, Any]:
    """prompts.yaml 파일 로드.

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때.
    """
    if not PROMPTS_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"필수 설정 파일을 찾을 수 없습니다: {PROMPTS_CONFIG_PATH}"
        )

    with PROMPTS_CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
        logger.info("프롬프트 설정 로드: %s", PROMPTS_CONFIG_PATH)
        return data if isinstance(data, dict) else {}


@lru_cache
def load_prompts_config() -> PromptsConfig:
    """프롬프트 설정 로드.

    Returns:
        PromptsConfig 인스턴스.

    Raises:
        FileNotFoundError: prompts.yaml 파일이 없을 때.
        ValueError: system 필드 누락 시.
    """
    data = _load_prompts_yaml()

    templates: dict[str, PromptTemplate] = {}

    for name, template_data in data.items():
        if not isinstance(template_data, dict):
            continue

        system = template_data.get("system")
        if not system:
            raise ValueError(
                f"템플릿 '{name}'의 'system' 필드가 누락되었습니다."
            )

        variables = {
            k: v for k, v in template_data.items()
            if k != "system"
        }

        templates[name] = PromptTemplate(
            name=name,
            system=system,
            variables=variables,
        )

    return PromptsConfig(templates=templates)


def get_prompt_template(name: str) -> PromptTemplate | None:
    """템플릿 이름으로 프롬프트 조회.

    Args:
        name: 템플릿 이름 (예: "summary", "key_extraction").

    Returns:
        PromptTemplate 또는 None.
    """
    config = load_prompts_config()
    return config.get_template(name)
