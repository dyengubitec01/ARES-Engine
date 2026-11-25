"""YAML 설정 로더 모듈.

config.yaml과 환경별 오버라이드 파일을 로드하고 병합한다.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# 프로젝트 루트 기준 config 디렉터리
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
CONFIG_DIR = PROJECT_ROOT / "config"


def _deep_merge(base: dict, override: dict) -> dict:
    """딕셔너리 깊은 병합.

    Args:
        base: 기본 설정.
        override: 오버라이드 설정.

    Returns:
        병합된 딕셔너리.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    """YAML 파일 로드.

    Args:
        path: YAML 파일 경로.

    Returns:
        파싱된 딕셔너리. 파일이 없으면 빈 딕셔너리.
    """
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def load_config() -> dict[str, Any]:
    """설정 로드 및 환경별 오버라이드 병합.

    1. config/config.yaml (기본 설정)
    2. config/config.{env}.yaml (환경별 오버라이드)

    Returns:
        병합된 설정 딕셔너리.
    """
    settings = get_settings()
    env = settings.app_env.value

    # 기본 설정 로드
    base_path = CONFIG_DIR / "config.yaml"
    base_config = _load_yaml(base_path)
    logger.info("기본 설정 로드: %s", base_path)

    # 환경별 오버라이드 로드 및 병합
    env_path = CONFIG_DIR / f"config.{env}.yaml"
    env_config = _load_yaml(env_path)

    if env_config:
        logger.info("환경별 설정 로드: %s", env_path)
    else:
        logger.debug("환경별 설정 파일 없음: %s", env_path)

    return _deep_merge(base_config, env_config)


def get_allowed_scopes() -> list[str]:
    """config.yaml에서 허용된 Scope 목록 조회.

    Returns:
        허용된 Scope 문자열 리스트.
    """
    scopes = get_config_value("scoping.allowed_scopes", [])
    return scopes if isinstance(scopes, list) else []


def get_config_value(key: str, default: Any = None) -> Any:
    """점(.) 표기법으로 설정값 조회.

    Args:
        key: 점으로 구분된 키 (예: "llm.default_timeout").
        default: 키가 없을 때 반환할 기본값.

    Returns:
        설정값 또는 기본값.

    Example:
        >>> get_config_value("llm.default_timeout")
        30
        >>> get_config_value("app.name")
        "TOL"
    """
    config = load_config()
    keys = key.split(".")

    value: Any = config
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    return value
