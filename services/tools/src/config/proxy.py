"""외부 API 프록시 설정 모듈.

config/proxy.yaml에서 프록시 대상 API 목록과 타임아웃/재시도 정책을 로드한다.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
PROXY_CONFIG_PATH = PROJECT_ROOT / "config" / "proxy.yaml"


@dataclass(frozen=True)
class ProxyTargetConfig:
    """개별 프록시 대상 API 설정."""

    name: str
    base_url: str
    description: str
    timeout: float
    max_retries: int
    headers: dict[str, str]


@dataclass(frozen=True)
class ProxyDefaults:
    """프록시 기본 설정."""

    timeout: float
    max_retries: int


@dataclass(frozen=True)
class ProxyConfig:
    """프록시 설정 전체."""

    defaults: ProxyDefaults
    targets: tuple[ProxyTargetConfig, ...]

    def get_target(self, name: str) -> ProxyTargetConfig | None:
        """이름으로 프록시 대상 API 조회."""
        for t in self.targets:
            if t.name == name:
                return t
        return None

    def get_target_names(self) -> list[str]:
        """등록된 프록시 대상 API 이름 목록."""
        return [t.name for t in self.targets]


def _load_proxy_yaml() -> dict[str, Any]:
    """proxy.yaml 파일 로드.

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때.
    """
    if not PROXY_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"필수 설정 파일을 찾을 수 없습니다: {PROXY_CONFIG_PATH}"
        )

    with PROXY_CONFIG_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
        logger.info("프록시 설정 로드: %s", PROXY_CONFIG_PATH)
        return data if isinstance(data, dict) else {}


@lru_cache
def load_proxy_config() -> ProxyConfig:
    """프록시 설정 로드.

    Returns:
        ProxyConfig 인스턴스.

    Raises:
        FileNotFoundError: proxy.yaml 파일이 없을 때.
    """
    data = _load_proxy_yaml()

    proxy_data = data.get("proxy", {})

    # defaults
    defaults_data = proxy_data.get("defaults", {})
    defaults = ProxyDefaults(
        timeout=float(defaults_data.get("timeout", 5.0)),
        max_retries=int(defaults_data.get("max_retries", 2)),
    )

    # targets
    targets_data = proxy_data.get("targets", [])
    targets: list[ProxyTargetConfig] = []

    for item in targets_data:
        if not isinstance(item, dict):
            continue
        if "name" not in item:
            logger.warning("프록시 대상에 name 필드 누락 — 건너뜀: %s", item)
            continue
        if "base_url" not in item:
            logger.warning("프록시 대상에 base_url 필드 누락 — 건너뜀: %s", item)
            continue

        targets.append(
            ProxyTargetConfig(
                name=item["name"],
                base_url=item["base_url"],
                description=item.get("description", ""),
                timeout=float(item.get("timeout", defaults.timeout)),
                max_retries=int(item.get("max_retries", defaults.max_retries)),
                headers=item.get("headers", {}),
            )
        )

    # 중복 이름 검증
    seen_names: set[str] = set()
    for t in targets:
        if t.name in seen_names:
            logger.warning("프록시 대상 이름 중복 — 무시: %s", t.name)
        seen_names.add(t.name)

    return ProxyConfig(defaults=defaults, targets=tuple(targets))
