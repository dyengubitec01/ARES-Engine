"""도구 정의 설정 모듈.

config/tools.yaml에서 도구 정의와 Scope 매핑을 로드한다.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
TOOLS_CONFIG_PATH = PROJECT_ROOT / "config" / "tools.yaml"


@dataclass(frozen=True)
class ToolConfig:
    """개별 도구 정의."""

    name: str
    endpoint: str
    description: str
    scopes: tuple[str, ...]
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolsConfig:
    """도구 설정 전체."""

    tools: tuple[ToolConfig, ...]

    def get_tools_by_scope(self, scope: str) -> tuple[ToolConfig, ...]:
        """Scope에 해당하는 도구만 필터링."""
        return tuple(t for t in self.tools if scope in t.scopes)

    def get_tool_by_endpoint(self, endpoint: str) -> ToolConfig | None:
        """엔드포인트 경로로 도구 검색."""
        return next((t for t in self.tools if t.endpoint == endpoint), None)


def _load_tools_yaml() -> dict[str, Any]:
    """tools.yaml 파일 로드.

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때.
    """
    if not TOOLS_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"필수 설정 파일을 찾을 수 없습니다: {TOOLS_CONFIG_PATH}"
        )

    with TOOLS_CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
        logger.info("도구 설정 로드: %s", TOOLS_CONFIG_PATH)
        return data if isinstance(data, dict) else {}


@lru_cache
def load_tools_config() -> ToolsConfig:
    """도구 설정 로드.

    Returns:
        ToolsConfig 인스턴스.

    Raises:
        FileNotFoundError: tools.yaml 파일이 없을 때.
    """
    data = _load_tools_yaml()

    tools_data = data.get("tools", [])
    tools: list[ToolConfig] = []

    for item in tools_data:
        if not isinstance(item, dict):
            continue
        if "name" not in item:
            logger.warning("도구 정의에 name 필드 누락 — 건너뜀: %s", item)
            continue

        tools.append(
            ToolConfig(
                name=item["name"],
                endpoint=item.get("endpoint", ""),
                description=item.get("description", ""),
                scopes=tuple(item.get("scopes", [])),
                parameters=item.get("parameters", {}),
            )
        )

    return ToolsConfig(tools=tuple(tools))
