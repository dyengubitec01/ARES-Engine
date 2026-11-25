import os
from functools import lru_cache

from pydantic_settings import BaseSettings


TRACE_ID_HEADER = "X-LF-Trace-ID"
PARENT_ID_HEADER = "X-LF-Parent-Id"

_APP_ENV = os.getenv("APP_ENV", "dev")


class Settings(BaseSettings):
    """애플리케이션 환경 설정. 모든 값은 .env.{APP_ENV} 또는 환경변수에서 주입."""

    # 앱 환경
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8006
    LOG_LEVEL: str = "DEBUG"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "documents"
    QDRANT_CONTENT_FIELD: str = "text_for_search"

    # Embedding API
    EMBEDDING_API_URL: str = "http://localhost:8100/query"

    # Reranker
    RERANKER_URL: str = "http://localhost:8011/rerank"

    # Langfuse
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # 검색 파라미터
    SEARCH_K: int = 20
    TOP_K: int = 6
    SCORE_THRESHOLD: float = 0.0  # 리랭킹 score 임계값 (0.0 = 필터링 없음)

    # Hybrid Search (Dense + BM25 + RRF)
    HYBRID_SEARCH_ENABLED: bool = False  # 인덱스 준비 후 운영자가 True로 토글
    RRF_K: int = 60                      # Reciprocal Rank Fusion 상수

    # Parent-document 인접 청크 확장 (실험적)
    PARENT_EXPANSION_ENABLED: bool = False  # True: 매칭 청크의 parent ±1 통째 회수·병합

    # HTTP 클라이언트
    HTTP_TIMEOUT: float = 30.0

    model_config = {
        "env_file": f".env.{_APP_ENV}",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Settings 싱글턴 반환."""
    return Settings()
