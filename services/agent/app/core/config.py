"""
Application Configuration using Pydantic Settings.

환경 변수 및 설정 관리 (DESIGN_SPEC.md Section 2.2)
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_ENV = os.getenv("APP_ENV", "dev")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=f".env.{_APP_ENV}",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Environment
    APP_ENV: Literal["dev", "prod", "test"] = "dev"

    # Application Info
    APP_VERSION: str = "1.0.0"

    # Logging
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    LOG_JSON_FORMAT: bool = False  # true: JSON (운영), false: 컬러 텍스트 (개발)
    LOG_APP_NAME: str = "agent"  # 서비스 이름 (agent / rag / tool)
    LOG_DIR: str = "/app/logs"  # 로그 파일 저장 디렉토리
    LOG_RETENTION_DAYS: int = 14  # 로그 보관 기간 (일)

    # LLM Server Configuration (On-premise, no API key required)
    PRIMARY_LLM_BASE_URL: str = "http://localhost:4000/v1"
    SECONDARY_LLM_BASE_URL: str = "http://localhost:4001/v1"

    # LLM Client Configuration
    LLM_API_KEY: str = "not-needed"
    LLM_TIMEOUT: float = 10.0
    LLM_MAX_TOKENS: int = Field(default=2048, gt=0)
    LLM_TEMPERATURE: float = Field(default=0.6, ge=0.0, le=2.0)

    # Health Check Configuration
    HEALTH_CHECK_TIMEOUT: float = 5.0

    # LangFuse Configuration (Optional - AC 1.5.6)
    LANGFUSE_TRACING_ENABLED: bool = True  # 명시적 on/off 스위치
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Response Configuration
    INCLUDE_THOUGHTS_IN_RESPONSE: bool = False  # 백엔드 준비되면 True로 변경

    # Workflow Configuration
    SKIP_REWRITER: bool = False  # True: 질문 재구성 건너뛰기 (원본 query 사용)
    SKIP_RAG: bool = False  # True: RAG 검색 건너뛰기 (context 없이 답변)
    SKIP_TOOL: bool = False  # True: Tool 실행 건너뛰기
    SKIP_DIRECT: bool = True  # True: direct 경로 비활성 (모든 질문 RAG 경유)
    USE_MOCK_RAG: bool = True  # True: MockRAGClient, False: RAGClient
    RAG_BASE_URL: str = "http://localhost:8006"
    RAG_TIMEOUT: float = 10.0

    # Tool Configuration (AC 2.4.5, Story 2.8: MCP → Tool rename)
    USE_MOCK_TOOL: bool = True  # True: MockToolClient, False: ToolClient
    TOOL_BASE_URL: str = "http://localhost:8007"
    TOOL_TIMEOUT: float = 30.0

    # LangFuse Prompt Management (Story 3.4)
    LANGFUSE_PROMPT_ENABLED: bool = True  # LangFuse 프롬프트 관리 on/off
    LANGFUSE_PROMPT_CACHE_TTL: int = 300  # 프롬프트 캐시 TTL (초)
    LANGFUSE_PROMPT_CONFIG_PATH: str = "config/prompts.yaml"

    # Model Configuration (Story 2.6)
    MODEL_CONFIG_PATH: str = "config/models.yaml"  # 환경별 설정 파일 경로

    @property
    def langfuse_enabled(self) -> bool:
        """Check if LangFuse tracing is enabled and configured.

        Returns True only if:
        - LANGFUSE_TRACING_ENABLED=true (명시적 on/off)
        - LANGFUSE_PUBLIC_KEY가 설정됨
        - LANGFUSE_SECRET_KEY가 설정됨
        """
        return (
            self.LANGFUSE_TRACING_ENABLED
            and bool(self.LANGFUSE_PUBLIC_KEY)
            and bool(self.LANGFUSE_SECRET_KEY)
        )

    @property
    def langfuse_prompt_enabled(self) -> bool:
        """Check if LangFuse prompt management is enabled and configured.

        Returns True only if:
        - LANGFUSE_PROMPT_ENABLED=true
        - LangFuse 자체가 활성화됨 (키 설정 포함)
        """
        return self.LANGFUSE_PROMPT_ENABLED and self.langfuse_enabled


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()


# =============================================================================
# Model Configuration (YAML-based)
# =============================================================================


class RoleConfig(BaseModel):
    """Individual role configuration."""

    model: str
    server: str
    fallback_role: str | None = None
    description: str = ""


class ServerConfig(BaseModel):
    """Server configuration."""

    base_url_env: str


class ModelConfig(BaseModel):
    """Model configuration loaded from models.yaml."""

    roles: dict[str, RoleConfig]
    servers: dict[str, ServerConfig]
    fallback_message: str = "서비스가 일시적으로 불안정합니다."

    def get_role(self, role_name: str) -> RoleConfig | None:
        """Get role configuration by name."""
        return self.roles.get(role_name)

    def get_model_for_role(self, role_name: str) -> str | None:
        """Get model name for a given role."""
        role = self.get_role(role_name)
        return role.model if role else None

    def get_server_url(self, role_name: str) -> str | None:
        """Get server URL for a given role."""
        role = self.get_role(role_name)
        if not role:
            return None

        server = self.servers.get(role.server)
        if not server:
            return None

        # Get URL from environment variable (with safe attribute access)
        env_var = server.base_url_env
        try:
            return getattr(settings, env_var, None)
        except (AttributeError, TypeError):
            return None

    def get_fallback_role(self, role_name: str) -> str | None:
        """Get fallback role for a given role."""
        role = self.get_role(role_name)
        return role.fallback_role if role else None


class ModelConfigError(Exception):
    """Error loading model configuration."""

    pass


def load_model_config(config_path: str | Path | None = None) -> ModelConfig:
    """
    Load model configuration from YAML file.

    Args:
        config_path: Path to models.yaml. Defaults to config/models.yaml.

    Returns:
        ModelConfig instance.

    Raises:
        ModelConfigError: If file not found or invalid YAML.
    """
    if config_path is None:
        config_path = Path("config/models.yaml")
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        raise ModelConfigError(f"Model config file not found: {config_path}")

    try:
        with open(config_path, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ModelConfigError(f"Invalid YAML in {config_path}: {e}") from e

    # yaml.safe_load는 빈 파일이나 None만 있는 경우 None을 반환할 수 있음
    if raw_data is None:
        raise ModelConfigError(f"Empty config file: {config_path}")

    if not isinstance(raw_data, dict):
        raise ModelConfigError(
            f"Invalid config format in {config_path}: expected dict, got {type(raw_data).__name__}"
        )

    data: dict[str, Any] = raw_data

    if "roles" not in data:
        raise ModelConfigError(f"Missing 'roles' section in {config_path}")

    if "servers" not in data:
        raise ModelConfigError(f"Missing 'servers' section in {config_path}")

    try:
        return ModelConfig(**data)
    except ValidationError as e:
        raise ModelConfigError(f"Invalid config schema in {config_path}: {e}") from e


@lru_cache
def get_model_config() -> ModelConfig:
    """Get cached model configuration instance (Singleton).

    Uses MODEL_CONFIG_PATH from settings (default: config/models.yaml).
    Can be overridden via environment variable for testing.
    """
    return load_model_config(settings.MODEL_CONFIG_PATH)


model_config = get_model_config()
