"""
Agent Server - Main Entry Point

FastAPI server for LangGraph-based AI Agent orchestration.
App Entrypoint & Global Exception Handler (DESIGN_SPEC.md Section 2.2)
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI

from app.api.v1 import chat_router, health_router, models_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.middleware import LoggingMiddleware

# Logging configuration (ADR-004)
configure_logging(
    json_format=settings.LOG_JSON_FORMAT,
    log_level=settings.LOG_LEVEL,
    app_name=settings.LOG_APP_NAME,
    log_dir=settings.LOG_DIR,
    retention_days=settings.LOG_RETENTION_DAYS,
)
from app.core.handlers import register_exception_handlers
from app.core.prompt_manager import prompt_manager
from app.core.tracing import tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown events."""
    # Startup: Eager initialization of tracing (AC 1.5.1)
    tracing.initialize()
    # Startup: Pre-fetch LangFuse prompts (AC 3.4.8)
    prompt_manager.prefetch_all()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Agent Server",
    description="LangGraph-based AI Agent Server",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Register middleware (ADR-004: request_id + Access Log)
app.add_middleware(LoggingMiddleware)

# Register global exception handlers (Story 1.6)
register_exception_handlers(app)

# Register API routers (Story 1.7, Story 2.6)
app.include_router(health_router)
app.include_router(models_router)
app.include_router(chat_router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
