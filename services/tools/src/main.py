"""TOL (Tool Server) FastAPI 앱 진입점."""

import importlib.metadata
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.exceptions import register_exception_handlers
from src.middleware import ScopeMiddleware, TraceIDMiddleware, flush_langfuse
from src.routers.summary import router as summary_router
from src.routers.tools import router as tools_router
from src.schemas.codes import TOLCode
from src.schemas.response import TOLResponse

logger = logging.getLogger(__name__)

try:
    _version = importlib.metadata.version("tol")
except importlib.metadata.PackageNotFoundError:
    _version = "0.0.0-dev"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 생명주기 관리.

    시작 시 초기화, 종료 시 정리 작업 수행.
    """
    # Startup
    logger.info("TOL 서버 시작 (version: %s)", _version)
    yield
    # Shutdown
    logger.info("TOL 서버 종료 중...")
    flush_langfuse()
    logger.info("TOL 서버 종료 완료")


app = FastAPI(
    title="TOL (Tool Server)",
    description="전사 공유형 AI 기능 거점 — AI Capability Hub",
    version=_version,
    lifespan=lifespan,
)

# 미들웨어 등록 (나중에 등록된 것이 바깥쪽에서 먼저 실행)
# 실행 순서: TraceID → Scope → Router
app.add_middleware(ScopeMiddleware)
app.add_middleware(TraceIDMiddleware)

# 전역 예외 핸들러 등록
register_exception_handlers(app)

# 라우터 등록
app.include_router(summary_router)
app.include_router(tools_router)


@app.get("/health", response_model=TOLResponse[dict])
def health_check() -> TOLResponse[dict]:
    """헬스체크 엔드포인트."""
    return TOLResponse.success(
        code=TOLCode.SUCCESS_QUERY,
        data={"status": "ok"},
    )
