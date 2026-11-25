"""시스템 프롬프트 템플릿 엔진.

config/prompts.yaml의 템플릿에 변수를 주입하여
LLM용 시스템 프롬프트를 생성한다.
"""

import logging
from typing import Any

from src.config.prompts import get_prompt_template

logger = logging.getLogger(__name__)


def render_system_prompt(
    template_name: str,
    **overrides: Any,
) -> str:
    """템플릿 이름으로 시스템 프롬프트를 렌더링.

    prompts.yaml에서 템플릿을 조회하고, 정의된 변수를 주입한다.
    overrides로 변수를 덮어쓸 수 있다.

    Args:
        template_name: 템플릿 이름 (예: "summary").
        **overrides: 변수 오버라이드 (예: target_n_tokens=500).

    Returns:
        변수가 주입된 시스템 프롬프트 문자열.

    Raises:
        ValueError: 템플릿이 존재하지 않거나 필수 변수가 누락된 경우.
    """
    template = get_prompt_template(template_name)
    if template is None:
        raise ValueError(f"프롬프트 템플릿 '{template_name}'을(를) 찾을 수 없습니다.")

    variables = {**template.variables, **overrides}

    try:
        rendered = template.system.format(**variables)
    except KeyError as exc:
        raise ValueError(
            f"템플릿 '{template_name}'의 필수 변수가 누락되었습니다: {exc}"
        ) from exc

    logger.info(
        "프롬프트 렌더링: template=%s, variables=%s",
        template_name,
        list(variables.keys()),
    )
    return rendered
