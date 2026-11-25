"""
LangFuse Prompt Management.

Story 3.4: LangFuse에서 프롬프트를 관리하고 코드 배포 없이 수정할 수 있도록 한다.
- AC 3.4.1: LangFuse 프롬프트 조회 + 환경별 라벨
- AC 3.4.2: Fallback 동작 (3단계)
- AC 3.4.3: 캐시 동작 (SDK Stale-While-Revalidate)
- AC 3.4.4: 비활성화

Fallback 체인: LangFuse fetch → fallback JSON → 코드 하드코딩
"""

import json
from pathlib import Path
from typing import Any

import structlog
import yaml
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings

logger = structlog.get_logger()

# fallback JSON 저장 경로
FALLBACK_DIR = Path("prompts/fallback")


class PromptConfig:
    """config/prompts.yaml 기반 프롬프트 메타데이터."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            config_path = Path(settings.LANGFUSE_PROMPT_CONFIG_PATH)
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Prompt config not found: {config_path}")

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self._prompts: dict[str, dict[str, Any]] = data.get("prompts", {})

    @property
    def prompt_names(self) -> list[str]:
        """등록된 프롬프트 이름 목록."""
        return list(self._prompts.keys())

    def get_variables(self, name: str) -> set[str]:
        """프롬프트에 기대되는 변수 목록."""
        entry = self._prompts.get(name)
        if not entry:
            raise KeyError(f"Unknown prompt: {name}")
        return set(entry.get("variables", []))

    def get_type(self, name: str) -> str:
        """프롬프트 타입 (chat / text)."""
        entry = self._prompts.get(name)
        if not entry:
            raise KeyError(f"Unknown prompt: {name}")
        return entry.get("type", "chat")


class PromptManager:
    """LangFuse 프롬프트 관리자.

    3단계 fallback 체인:
    1. LangFuse fetch (SDK 캐시 포함)
    2. fallback JSON (CI/CD에서 생성)
    3. 코드 하드코딩 프롬프트 (최후 보루)
    """

    def __init__(self, config: PromptConfig | None = None) -> None:
        self._config = config or PromptConfig()
        self._langfuse_client: Any = None

    def _get_label(self) -> str:
        """LangFuse 프롬프트 라벨.

        환경 분리는 LangFuse 프로젝트(API 키)로 처리되므로
        라벨은 항상 'production'을 사용한다.
        """
        return "production"

    def _get_langfuse(self) -> Any:
        """LangFuse 클라이언트 (lazy init)."""
        if self._langfuse_client is None:
            from langfuse import Langfuse

            self._langfuse_client = Langfuse()
        return self._langfuse_client

    def _load_fallback_json(self, name: str) -> list[tuple[str, str]] | None:
        """fallback JSON 파일에서 프롬프트 메시지 로드."""
        path = FALLBACK_DIR / f"{name}.json"
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return [(msg["role"], msg["content"]) for msg in data["messages"]]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(
                "langfuse_fallback_json_invalid",
                prompt_name=name,
                error=str(e),
            )
            return None

    def validate_variables(self, name: str, actual_variables: set[str]) -> None:
        """프롬프트 변수가 prompts.yaml 기대 목록과 일치하는지 검증."""
        expected = self._config.get_variables(name)
        if actual_variables != expected:
            raise ValueError(
                f"Variable mismatch for '{name}': "
                f"expected {sorted(expected)}, got {sorted(actual_variables)}"
            )

    def get_prompt(
        self,
        name: str,
        *,
        fallback_messages: list[tuple[str, str]] | None = None,
    ) -> ChatPromptTemplate:
        """LangFuse에서 프롬프트를 가져오고, 실패 시 fallback 체인을 따른다.

        Args:
            name: prompts.yaml에 정의된 프롬프트 이름.
            fallback_messages: 코드 하드코딩 프롬프트 (3순위 fallback).
                [(role, content), ...] 형태.

        Returns:
            ChatPromptTemplate 인스턴스.

        Fallback 체인:
            1순위: LangFuse fetch (캐시 포함)
            2순위: fallback JSON (CI/CD에서 생성)
            3순위: fallback_messages (코드 하드코딩)
        """
        prompt_type = self._config.get_type(name)

        # 1순위: LangFuse fetch
        if settings.langfuse_prompt_enabled:
            try:
                langfuse = self._get_langfuse()
                lf_prompt = langfuse.get_prompt(
                    name,
                    label=self._get_label(),
                    type=prompt_type,
                    cache_ttl_seconds=settings.LANGFUSE_PROMPT_CACHE_TTL,
                )

                if not lf_prompt.is_fallback:
                    langchain_messages = lf_prompt.get_langchain_prompt()
                    template = ChatPromptTemplate.from_messages(
                        langchain_messages,
                    )
                    template.metadata = {"langfuse_prompt": lf_prompt}
                    return template
            except Exception as e:
                logger.warning(
                    "langfuse_prompt_fetch_failed",
                    prompt_name=name,
                    error=str(e),
                )

        # 2순위: fallback JSON
        json_messages = self._load_fallback_json(name)
        if json_messages is not None:
            logger.warning(
                "langfuse_prompt_fallback",
                prompt_name=name,
                source="json",
            )
            return ChatPromptTemplate.from_messages(json_messages)

        # 3순위: 코드 하드코딩
        if fallback_messages is not None:
            logger.warning(
                "langfuse_prompt_fallback",
                prompt_name=name,
                source="hardcoded",
            )
            return ChatPromptTemplate.from_messages(fallback_messages)

        raise RuntimeError(
            f"No prompt available for '{name}': "
            "LangFuse fetch failed, no fallback JSON, no hardcoded fallback"
        )

    def prefetch_all(self) -> None:
        """앱 시작 시 모든 프롬프트를 pre-fetch하여 캐시에 적재."""
        if not settings.langfuse_prompt_enabled:
            logger.info("langfuse_prompt_prefetch_skipped", reason="disabled")
            return

        label = self._get_label()
        for name in self._config.prompt_names:
            prompt_type = self._config.get_type(name)
            try:
                langfuse = self._get_langfuse()
                langfuse.get_prompt(
                    name,
                    label=label,
                    type=prompt_type,
                    cache_ttl_seconds=settings.LANGFUSE_PROMPT_CACHE_TTL,
                )
                logger.info(
                    "langfuse_prompt_prefetched",
                    prompt_name=name,
                    label=label,
                )
            except Exception as e:
                logger.warning(
                    "langfuse_prompt_prefetch_failed",
                    prompt_name=name,
                    error=str(e),
                )


# Global prompt manager instance (Singleton)
prompt_manager = PromptManager()
