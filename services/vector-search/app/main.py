"""FastAPI 애플리케이션 팩토리 및 글로벌 예외 핸들러."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.responses import RAGCode, error_response
from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.exceptions import RAGBaseException
from app.core.interfaces import VectorStoreInterface
from app.core.monitoring import (
    LangfuseMiddleware,
    get_langfuse_client,
    shutdown_langfuse,
)
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


async def disable_hybrid_if_fulltext_index_missing(
    settings: Settings,
    vector_store: VectorStoreInterface,
) -> None:
    """앱 startup 시 Hybrid Search 가동 가능 여부를 읽기 전용으로 확인한다.

    HYBRID_SEARCH_ENABLED=True인데 text_for_search 필드에 full-text index가
    없으면 해당 플래그를 런타임에 False로 비활성화하여 dense-only 모드로
    안전하게 기동한다. 앱이 인덱스를 생성하지는 않는다(검색 전용 원칙 준수).
    """
    if not settings.HYBRID_SEARCH_ENABLED:
        return

    try:
        has_index = await vector_store.check_fulltext_index()
    except Exception as exc:
        logger.warning(
            "Fulltext index 검증 중 오류 — Hybrid Search 비활성화: cause=%s", exc,
        )
        settings.HYBRID_SEARCH_ENABLED = False
        return

    if not has_index:
        logger.error(
            "Hybrid Search 비활성화: collection=%s 에 text_for_search full-text index "
            "가 없습니다. dense-only로 동작합니다. 운영자는 인덱스 생성 후 "
            "HYBRID_SEARCH_ENABLED=true로 재시작하세요.",
            settings.QDRANT_COLLECTION,
        )
        settings.HYBRID_SEARCH_ENABLED = False


def create_app() -> FastAPI:
    """FastAPI 애플리케이션 팩토리."""
    settings = get_settings()

    # 로깅 설정
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.DEBUG),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # /health access log 필터링
    class _HealthFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "/health" not in getattr(record, "message", record.getMessage())

    logging.getLogger("uvicorn.access").addFilter(_HealthFilter())

    # DI: 어댑터 바인딩
    from app.adapters.embedding_adapter import EmbeddingAdapter
    from app.adapters.qdrant_adapter import QdrantAdapter
    from app.adapters.reranker_adapter import RerankerAdapter

    embedding = EmbeddingAdapter(settings)
    vector_store = QdrantAdapter(settings=settings)
    reranker = RerankerAdapter(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await disable_hybrid_if_fulltext_index_missing(settings, vector_store)
        yield
        shutdown_langfuse()

    app = FastAPI(
        title="RAG Search Server",
        description="Lightweight RAG Search Server - Retriever & Reranker for agent systems",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Langfuse 미들웨어 등록
    langfuse_client = get_langfuse_client()
    app.add_middleware(LangfuseMiddleware, langfuse_client=langfuse_client)

    app.state.search_service = SearchService(
        embedding=embedding,
        vector_store=vector_store,
        reranker=reranker,
        settings=settings,
    )

    # 라우터 등록
    app.include_router(router)

    # === 글로벌 예외 핸들러 ===

    @app.exception_handler(RAGBaseException)
    async def rag_exception_handler(
        request: Request, exc: RAGBaseException
    ) -> JSONResponse:
        """커스텀 예외 → 표준 에러 응답 변환."""
        logger.error(
            "RAGBaseException: code=%s msg=%s path=%s",
            exc.code.value,
            exc.msg,
            request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(code=exc.code, msg=exc.msg),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Pydantic 유효성 검증 실패 → RAG100020 변환."""
        logger.warning(
            "RequestValidationError: path=%s errors=%s",
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=400,
            content=error_response(code=RAGCode.BAD_REQUEST),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """FastAPI/Starlette 내장 HTTP 예외 → 표준 응답 형식 변환."""
        logger.warning(
            "HTTPException: status=%d detail=%s path=%s",
            exc.status_code,
            exc.detail,
            request.url.path,
        )
        msg = None
        if settings.APP_ENV != "prod" and exc.detail:
            msg = str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(code=RAGCode.BAD_REQUEST, msg=msg),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """미처리 예외 → RAG100099 변환. 스택 트레이스는 로그에만 기록."""
        logger.exception(
            "Unhandled exception: path=%s", request.url.path
        )
        return JSONResponse(
            status_code=500,
            content=error_response(code=RAGCode.INTERNAL_ERROR),
        )

    # === 헬스체크 ===

    @app.get("/health")
    async def health_check() -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "env": settings.APP_ENV},
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_ENV == "dev",
    )
