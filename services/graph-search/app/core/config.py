"""Settings (env 기반 설정) + get_settings()."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings

TRACE_ID_HEADER = "X-LF-Trace-ID"
PARENT_ID_HEADER = "X-LF-Parent-Id"

_APP_ENV = os.getenv("APP_ENV", "dev")


class Settings(BaseSettings):
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8007
    LOG_LEVEL: str = "DEBUG"

    # Graph flag
    GRAPH_ENABLED: bool = False

    # Postgres
    POSTGRES_URL: str = ""
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_SEARCH_PATH: str = "rag,public"

    # GLiNER
    GLINER_URL: str = ""
    GLINER_API_KEY: str = ""

    # Qdrant (entity)
    QDRANT_URL: str = "http://localhost:6333"
    ENTITY_COLLECTION: str = "rag_graph_entities_v1"

    # Embedding
    EMBEDDING_URL: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_MODEL: str = "embed-bge-m3"

    # Tuning
    GRAPH_COSINE_THRESHOLD: float = 0.85
    GRAPH_NEIGHBOR_LIMIT: int = 30
    GRAPH_CHUNK_LIMIT: int = 20

    # Langfuse
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # HTTP
    HTTP_TIMEOUT: float = 30.0

    model_config = {
        "env_file": f".env.{_APP_ENV}",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
