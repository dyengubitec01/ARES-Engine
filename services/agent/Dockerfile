FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 + uv 설치
COPY --from=ghcr.io/astral-sh/uv:0.9.10 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 의존성 먼저 설치 (레이어 캐싱) — uv.lock 기반 버전 고정
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --extra tracing --no-dev --no-install-project

# 소스 및 설정 복사
COPY app/ ./app/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY prompts/ ./prompts/
COPY main.py ./
RUN uv sync --frozen --extra tracing --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
