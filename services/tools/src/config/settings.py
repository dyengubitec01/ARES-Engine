"""환경변수 기반 설정 모듈.

.env 파일에서 민감 정보(API Key, URL 등)를 로드한다.
"""

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(str, Enum):
    """애플리케이션 실행 환경."""

    DEVELOPMENT = "development"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """환경변수 기반 설정.

    .env 파일 또는 시스템 환경변수에서 값을 로드한다.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    app_env: AppEnv = Field(default=AppEnv.DEVELOPMENT)

    # LLM Infrastructure
    llm_gateway_url: str = Field(default="http://localhost:4000/v1")
    llm_api_key: str = Field(default="")

    # Langfuse
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="")

    @property
    def is_production(self) -> bool:
        """운영 환경 여부."""
        return self.app_env == AppEnv.PRODUCTION

    @property
    def is_development(self) -> bool:
        """개발 환경 여부."""
        return self.app_env == AppEnv.DEVELOPMENT


@lru_cache
def get_settings() -> Settings:
    """설정 싱글턴 인스턴스 반환."""
    return Settings()
