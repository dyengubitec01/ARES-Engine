"""FastAPI 팩토리, DI 배선, 예외 핸들러, 헬스체크."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.responses import RAGCode, error_response
from app.api.routes import router
from app.core.config import get_settings
from app.core.exceptions import RAGBaseException
from app.core.monitoring import (
    LangfuseMiddleware,
    get_langfuse_client,
    shutdown_langfuse,
)


def create_app() -> FastAPI:
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.DEBUG),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from app.adapters.embedding_adapter import EmbeddingAdapter
    from app.adapters.entity_qdrant_adapter import EntityQdrantAdapter
    from app.adapters.gliner_adapter import GLinerAdapter
    from app.adapters.postgres_adapter import PostgresAdapter
    from app.services.graph_retriever import GraphRetriever

    embedding = EmbeddingAdapter(settings)
    postgres = PostgresAdapter(settings)
    graph_retriever = GraphRetriever(
        settings=settings,
        gliner=GLinerAdapter(settings),
        postgres=postgres,
        entity_store=EntityQdrantAdapter(settings),
        embedding=embedding,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await postgres.close()
        shutdown_langfuse()

    app = FastAPI(title="RAG Graph Search Server", lifespan=lifespan)
    app.state.graph_retriever = graph_retriever

    langfuse_client = get_langfuse_client()
    app.add_middleware(LangfuseMiddleware, langfuse_client=langfuse_client)
    app.include_router(router)

    @app.exception_handler(RAGBaseException)
    async def _rag_exc_handler(request: Request, exc: RAGBaseException) -> JSONResponse:
        return JSONResponse(status_code=200, content={"code": exc.code, "msg": exc.msg})

    @app.exception_handler(Exception)
    async def _unhandled_exc_handler(request: Request, exc: Exception) -> JSONResponse:
        # Fail-open: 내부 예외도 200 엔벨로프로 흡수
        logging.getLogger(__name__).warning("처리되지 않은 예외 흡수: %s", exc)
        return JSONResponse(
            status_code=200,
            content=error_response(RAGCode.GRAPH_STORE_ERROR),
        )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
