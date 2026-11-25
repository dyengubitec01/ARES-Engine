# TOL (Tool Server)

전사 공유형 AI 기능 거점 — **AI Capability Hub**

## 1. 서버 개요

에이전트 서버가 호출하는 공통 AI 기능(요약, 도구 관리, 외부 API 프록시)을 REST API로 제공하는 Tool Server입니다. LLM Gateway를 통해 모델을 호출하고, Langfuse로 cross-service tracing을 지원합니다.

### 시스템 구성도

```
              ┌──────────────┐
              │ Agent Server │
              └──────┬───────┘
                     │ REST (JSON)
                     │ X-LF-Trace-ID, X-LF-Parent-Id, X-TOL-Scope
                     ▼
              ┌──────────────┐
              │  TOL Server  │
              │    :8007     │
              └──┬────────┬──┘
                 │        │
                 ▼        ▼
        ┌────────────┐ ┌─────────────────┐
        │LLM Gateway │ │    Langfuse     │
        │            │ │ (Observability) │
        └────────────┘ └─────────────────┘
```

### 통신 프로토콜

| 통신 경로 | 프로토콜 | 커스텀 헤더 | 설명 |
|-----------|----------|------------|------|
| Agent → TOL | REST (JSON) | `X-LF-Trace-ID`, `X-LF-Parent-Id`, `X-TOL-Scope` | Scope 검증 + cross-service tracing |
| TOL → LLM Gateway | REST (JSON) | `Authorization: Bearer {API_KEY}` | OpenAI-compatible API |
| TOL → Langfuse | REST (SDK) | — | Langfuse SDK v3 자동 전송 |

## 2. 기술 스택

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.11+ |
| Web Framework | FastAPI | >=0.104, <1.0 |
| HTTP Client | httpx | >=0.25, <1.0 |
| Validation | Pydantic v2 + pydantic-settings | >=2.0, <3.0 |
| Config | PyYAML | >=6.0, <7.0 |
| Observability | Langfuse SDK v3 | >=3.8, <4.0 |
| Test | pytest, respx | — |
| Containerization | Docker | — |
| CI/CD | Jenkins | Declarative Pipeline |
| Package | pip + pyproject.toml | — |

## 3. 빠른 시작

### Prerequisites

- Python 3.11+
- pip

### Installation

```bash
# Clone repository
git clone <repository-url>
cd Tools-REST-API

# 가상환경 생성 + 의존성 설치
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -e ".[dev]"

# 환경변수 설정
cp .env.example .env
```

### Configuration

`.env` 파일을 환경에 맞게 설정합니다.

```bash
# LLM Gateway 연결
LLM_GATEWAY_URL=http://localhost:4000/v1
LLM_API_KEY=your-api-key-here

# Langfuse (선택 — 미설정 시 트레이싱 비활성화, 서버는 정상 동작)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=

# 서버 환경
APP_ENV=development
```

> 전체 환경변수 목록은 [6. 설정 — 환경변수](#환경변수) 참조

### Running

```bash
# 개발 서버 (hot-reload)
uvicorn src.main:app --reload --port 8007
```

- Swagger UI: http://localhost:8007/docs
- 헬스체크: http://localhost:8007/health

## 4. API 엔드포인트

| Endpoint | Method | Description | Scope 필요 |
|----------|--------|-------------|-----------|
| `/health` | GET | 헬스체크 | X |
| `/v1/tools` | GET | Scope 기반 도구 목록 (OpenAI Function Calling Spec) | O (`agent`, `backend`) |
| `/v1/summary` | POST | 대화 이력 기반 요약 | O (`agent`, `backend`) |

### 표준 응답 형식

모든 응답은 TOL 표준 포맷을 따른다:

```json
{
  "code": "TOL020100",
  "msg": "요청이 성공했습니다",
  "data": { ... }
}
```

`trace_id`는 응답 헤더 `X-LF-Trace-ID`로 반환된다.

### 응답 코드

| 코드 | HTTP | 구분 | 의미 |
|------|------|------|------|
| `TOL010100` | 200 | 성공 | 조회 성공 |
| `TOL020100` | 200 | 성공 | 요약 성공 |
| `TOL000021` | — | 정보 | Trace-ID 자동 생성 |
| `TOL010130` | 400 | 에러 | 유효하지 않은 Scope |
| `TOL020130` | 503 | 에러 | LLM 프로바이더 응답 실패 |
| `TOL030130` | 502 | 에러 | 외부 API 호출 실패 |
| `TOL000030` | 500 | 에러 | 서버 내부 오류 |

### POST /v1/summary 요청

```json
{
  "history": [
    { "role": "user", "content": "그래서 결론이 뭐야?" },
    { "role": "assistant", "content": "핵심은 ...입니다." }
  ],
  "summary": "이전 대화 요약 내용 (선택)"
}
```

- `history`: `ChatMessage[]` (최소 1건, `role`은 `user` | `assistant`)
- `summary`: 이전 요약 텍스트 (갱신 시 전달, 첫 요약 시 생략)

### GET /v1/tools 응답 (OpenAI Function Calling Spec)

```json
{
  "code": "TOL010100",
  "msg": "요청이 성공했습니다",
  "data": {
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "summary",
          "description": "텍스트 요약 — 긴 텍스트를 설정된 분량에 맞게 요약",
          "parameters": { ... }
        }
      }
    ]
  }
}
```

## 5. 프로젝트 구조

```
Tools-REST-API/
├── src/
│   ├── main.py                  # FastAPI 앱 진입점, lifespan
│   ├── config/                  # 설정 로더 (YAML + .env)
│   │   ├── loader.py            #   config.yaml 로더 (deep merge, 환경별 오버라이드)
│   │   ├── settings.py          #   Pydantic Settings (.env 로드)
│   │   ├── models.py            #   models.yaml 파서 (Role-Based 모델 매핑)
│   │   ├── prompts.py           #   prompts.yaml 로더
│   │   ├── proxy.py             #   proxy.yaml 로더
│   │   └── tools.py             #   tools.yaml 로더
│   ├── middleware/               # 미들웨어
│   │   ├── trace_id.py          #   Trace-ID 추출/생성 + Langfuse root span
│   │   ├── langfuse.py          #   Langfuse 클라이언트, ManagedSpan, create_span
│   │   └── scope.py             #   X-TOL-Scope 검증 (tools.yaml 기반)
│   ├── routers/                  # API 라우터
│   │   ├── summary.py           #   POST /v1/summary
│   │   └── tools.py             #   GET /v1/tools
│   ├── services/                 # 비즈니스 로직
│   │   ├── summary.py           #   요약 서비스
│   │   ├── scoping.py           #   도구 필터링 (Scope)
│   │   ├── proxy.py             #   외부 API 프록시
│   │   └── prompt_engine.py     #   프롬프트 템플릿 렌더링
│   ├── providers/                # LLM Provider
│   │   ├── base.py              #   BaseLLMProvider ABC
│   │   ├── gateway.py           #   GatewayProvider (httpx → LLM Gateway)
│   │   └── deps.py              #   FastAPI DI (get_llm_provider)
│   ├── schemas/                  # Pydantic 모델
│   │   ├── codes.py             #   TOLCode, TOLMessage Enum
│   │   ├── response.py          #   TOLResponse[T] Generic
│   │   ├── summary.py           #   SummaryRequest, ChatMessage, SummaryData
│   │   └── tools.py             #   ToolDefinition, ToolsData
│   └── exceptions/               # 예외 처리
│       ├── exceptions.py         #   LLMProviderError, InvalidScopeError, ExternalAPIError
│       └── handlers.py           #   전역 예외 핸들러 등록
├── config/
│   ├── config.yaml               # 기본 설정
│   ├── config.development.yaml   # 개발 오버라이드
│   ├── config.production.yaml    # 운영 오버라이드
│   ├── models.yaml               # Role-Based 모델 매핑 + fallback 체인
│   ├── prompts.yaml              # 프롬프트 템플릿
│   ├── proxy.yaml                # 외부 API 프록시 대상
│   └── tools.yaml                # 도구 정의 + Scope 매핑
├── tests/                        # 테스트 (218건)
├── Dockerfile                    # 컨테이너 빌드
├── docker-compose.yml            # 운영 배포 설정
├── Jenkinsfile                   # CI/CD 파이프라인
└── pyproject.toml                # 의존성 및 빌드 설정
```

### Layered Architecture

```
Request → TraceIDMiddleware → ScopeMiddleware → Router → Service → Provider → LLM Gateway
```

미들웨어 실행 순서: **TraceID → Scope → Router** (나중에 등록된 것이 바깥쪽에서 먼저 실행).

## 6. 설정

TOL 서버는 **Config-Driven 아키텍처**로, 코드 수정 없이 YAML 파일만으로 모델 교체, 도구 추가, 프롬프트 변경이 가능하다.

### YAML 설정 파일

| 파일 | 역할 | 상세 가이드 |
|------|------|-----------|
| `config/config.yaml` | LLM, 로깅, 스코핑 기본 설정 | — |
| `config/models.yaml` | Role-Based 모델 매핑 + fallback 체인 | [모델 설정 가이드](wiki/guides/model-configuration.md) |
| `config/tools.yaml` | 도구 정의 + Scope 매핑 | [도구 추가 가이드](wiki/guides/add-tool.md) |
| `config/prompts.yaml` | 프롬프트 템플릿 (`{target_n_tokens}` 치환) | — |
| `config/proxy.yaml` | 외부 API 프록시 대상 + 재시도 설정 | — |

환경별 오버라이드: `config.development.yaml` (DEBUG, timeout 60s), `config.production.yaml` (WARNING, timeout 30s).

### 환경변수

`.env` 파일 또는 시스템 환경변수에서 로드. `.env.example` 참조.

#### Server

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `APP_ENV` | 실행 환경 (`development` / `production`) | `development` |

#### LLM

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `LLM_GATEWAY_URL` | LLM Gateway 엔드포인트 | `http://localhost:4000/v1` |
| `LLM_API_KEY` | Gateway 인증 API Key | (빈 문자열) |

#### Langfuse

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `LANGFUSE_PUBLIC_KEY` | Langfuse Public Key | (빈 문자열) |
| `LANGFUSE_SECRET_KEY` | Langfuse Secret Key | (빈 문자열) |
| `LANGFUSE_HOST` | Langfuse 서버 호스트 URL | (빈 문자열) |

> Langfuse 키가 비어 있으면 트레이싱이 비활성화된다 (서버는 정상 동작).

## 7. 배포/운영

### Docker 빌드

```bash
docker build -t tools-rest-api .
```

- **베이스 이미지**: `python:3.11-slim`
- **의존성 설치**: `pip install --no-cache-dir .`
- **헬스체크**: 30초 간격, `curl -f http://localhost:8007/health`
- **포트**: 8007

### docker-compose.yml (운영)

```bash
docker compose up -d
```

| 항목 | 설정 |
|------|------|
| 이미지 | `registry.example.com/ares/tools-rest-api:latest` |
| 포트 | `8007:8007` |
| 환경변수 | `.env` 파일 마운트 |
| 볼륨 | `./logs:/app/logs` (로그 파일) |
| 로그 출력 | `uvicorn ... 2>&1 \| tee -a /app/logs/app.log` |
| 헬스체크 | 30초 간격, `/health` 엔드포인트 |
| 로그 로테이션 | `json-file`, max 10MB x 10개 |
| 재시작 정책 | `unless-stopped` |

### Jenkins CI/CD 파이프라인

```
Checkout → Docker Build → Docker Push → Deploy
```

1. **Checkout**: 소스코드 체크아웃
2. **Docker Build**: 이미지 빌드 (빌드 번호 + latest 태그)
3. **Docker Push**: 사내 레지스트리에 이미지 Push
4. **Deploy**: SSH로 배포 서버에 `.env` + `docker-compose.yml` 전달 → `docker compose pull && up -d`

## 8. 개발 가이드

### 커스터마이징

- **모델 변경**: `config/models.yaml`에서 역할별 모델명 수정 → [모델 설정 가이드](wiki/guides/model-configuration.md)
- **도구 추가**: `config/tools.yaml`에 정의 + 라우터/서비스 구현 → [도구 추가 가이드](wiki/guides/add-tool.md)
- **프롬프트 수정**: `config/prompts.yaml`에서 템플릿 편집

### 테스트

총 **218개** 단위 테스트, 13개 파일. 상세 목록은 [테스트 문서](wiki/tests.md)를 참조하세요.

```bash
# 전체 실행
pytest tests/

# 상세 출력
pytest tests/ -v

# 특정 파일
pytest tests/test_trace_id.py -v

# 특정 클래스
pytest tests/test_trace_id.py::TestTraceIDMiddleware -v

# 패턴 필터
pytest tests/ -k "test_trace"

# 커버리지
pytest tests/ --cov=src --cov-report=term-missing
```

#### E2E 테스트

Langfuse 실환경 연결 테스트. `LANGFUSE_PUBLIC_KEY` 환경변수 미설정 시 자동 스킵.

```bash
pytest tests/test_langfuse_e2e.py -v
```

## 9. 문서

- **가이드**
  - [모델 설정](wiki/guides/model-configuration.md)
  - [도구 추가](wiki/guides/add-tool.md)
  - [Langfuse 트레이싱 아키텍처](wiki/guides/langfuse-tracing.md)
- [테스트 문서](wiki/tests.md)
