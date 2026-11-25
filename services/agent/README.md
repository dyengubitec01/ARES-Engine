# Agent Server

LangGraph 기반 지능형 에이전트 오케스트레이션 서버

## 1. 서버 개요

사용자의 복합적인 질문과 대화 문맥을 이해하고, 의도를 분류(Router)하여 외부 도구(Tool Server)와 지식(RAG Server)을 활용해 최적의 답변을 생성하는 AI Agent Server입니다.

### 시스템 구성도

```
                    ┌─────────────────────────┐
                    │      Agent Server       │
                    │  (LangGraph Workflow)    │
                    └────┬──────┬──────┬──────┘
                         │      │      │
             ┌───────────┘      │      └───────────┐
             ▼                  ▼                   ▼
   ┌──────────────────┐ ┌────────────┐ ┌──────────────────┐
   │   LLM Gateway    │ │ RAG Server │ │   Tool Server    │
   │ Primary/Secondary│ │            │ │                  │
   └──────────────────┘ └────────────┘ └──────────────────┘
                                │               │
                         X-LF-Trace-ID    X-LF-Trace-ID
                         X-LF-Parent-Id   X-LF-Parent-Id
                                          X-TOL-Scope
                                ▼               ▼
                         ┌────────────────────────┐
                         │   LangFuse (Optional)   │
                         │ Observability + Prompts │
                         └────────────────────────┘
```

LangFuse는 트레이싱뿐 아니라 **프롬프트 관리**(Prompt Management)도 담당합니다. 자세한 내용은 [6.4 프롬프트 관리](#64-프롬프트-관리-langfuse)를 참조하세요.

### 통신 프로토콜

| 통신 경로 | 프로토콜 | 커스텀 헤더 | 설명 |
|-----------|----------|------------|------|
| Agent → LLM Gateway | REST (OpenAI-compatible) | — | LangChain ChatOpenAI 클라이언트 |
| Agent → RAG Server | REST (httpx) | `X-LF-Trace-ID`, `X-LF-Parent-Id` | `POST /v1/search` 문서 검색 |
| Agent → Tool Server | REST (httpx) | `X-TOL-Scope`, `X-LF-Trace-ID`, `X-LF-Parent-Id` | `GET /v1/tools`, `POST /v1/{tool_name}` |
| Client → Agent | SSE over HTTP | — | `POST /v1/chat` 스트리밍 응답 |
| Agent → LangFuse | REST (SDK) | — | 트레이싱 + 프롬프트 fetch |

## 2. 기술 스택

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.11+ |
| Web Framework | FastAPI | >=0.109.0 |
| AI Orchestration | LangGraph | >=0.2.0 |
| LLM Integration | LangChain + LangChain-OpenAI | >=0.3.0 |
| Validation | Pydantic v2 + pydantic-settings | >=2.0 |
| HTTP Client | httpx | >=0.25.0 |
| Logging | structlog | >=24.1.0 |
| Package Manager | uv | — |
| Tracing / Prompts (optional) | LangFuse SDK v3 | >=3.8.0 |
| Containerization | Docker | — |
| CI/CD | Jenkins | Declarative Pipeline |

## 3. 빠른 시작

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd agent

# 가상환경 생성 + 의존성 설치 (tracing 포함)
# uv가 .venv를 자동 생성하고, uv.lock 기반으로 정확한 버전을 설치합니다.
uv sync --all-extras

# 환경변수 파일 생성 (APP_ENV에 따라 파일명이 결정됨 — 아래 참조)
cp .env.example .env.dev
```

> `uv sync`는 `pyproject.toml`의 의존성을 `uv.lock` lockfile에 맞춰 설치하는 명령어입니다.
> `--all-extras`는 optional dependencies(tracing, dev)를 모두 포함합니다.
> 가상환경(`.venv/`)이 없으면 자동으로 생성됩니다.

### 환경 파일 로딩 규칙

설정은 OS 환경변수 `APP_ENV`(기본값 `dev`)에 따라 **`.env.{APP_ENV}`** 파일에서 로드됩니다.

| `APP_ENV` | 로드되는 파일 |
|-----------|--------------|
| `dev` (기본값) | `.env.dev` |
| `prod` | `.env.prod` |
| `test` | `.env.test` |

Docker 배포 시에는 compose의 `env_file: .env`로 값이 OS 환경변수에 주입되므로 파일명 규칙과 무관하게 동작합니다.

### Configuration

`.env.dev` 파일을 환경에 맞게 설정합니다. LLM 연결 방식에 따라 두 가지 시나리오가 있습니다.

#### A. 로컬 개발 (Ollama)

Ollama를 설치하고 모델을 다운로드한 뒤 연결합니다. 자세한 설치 방법은 [Ollama 설정 가이드](wiki/guides/ollama-setup.md)를 참조하세요.

```bash
# Ollama 서버 (OpenAI 호환 API, 기본 포트 11434)
PRIMARY_LLM_BASE_URL=http://localhost:11434/v1
SECONDARY_LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=not-needed

# Ollama는 모델 로딩 시간이 필요하므로 타임아웃 여유 있게 설정
LLM_TIMEOUT=120.0

# 로컬 테스트용 모델 설정 (Ollama 모델: qwen2.5:7b, qwen2.5:3b)
MODEL_CONFIG_PATH=config/models.test.yaml

# RAG/Tool 서버 없이 개발
USE_MOCK_RAG=true
USE_MOCK_TOOL=true

# LangFuse 없이 개발 (코드 하드코딩 프롬프트 사용)
LANGFUSE_TRACING_ENABLED=false
LANGFUSE_PROMPT_ENABLED=false
```

#### B. 운영 환경 (On-Premise GPU 서버)

사내 GPU 서버에서 제공하는 OpenAI-compatible API에 연결합니다.

```bash
# 주 GPU 서버 + 백업 서버 (Failover)
PRIMARY_LLM_BASE_URL=http://your-gpu-server:4000/v1
SECONDARY_LLM_BASE_URL=http://your-backup-server:4000/v1
LLM_API_KEY=your-api-key
LLM_TIMEOUT=10.0

# 운영 모델 설정 (chat-gemma-27b, chat-deepseek-r1-14b 등)
MODEL_CONFIG_PATH=config/models.yaml

# 실제 RAG/Tool 서버 연결
USE_MOCK_RAG=false
RAG_BASE_URL=http://your-rag-server:8006
USE_MOCK_TOOL=false
TOOL_BASE_URL=http://your-tool-server:8007
```

> 전체 환경변수 목록은 [7. 환경변수](#7-환경변수) 참조

### Running

```bash
# 개발 서버 (hot-reload)
uv run uvicorn main:app --reload

# 프로덕션
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

## 4. API 엔드포인트

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | 헬스체크 |
| `/health?deep=true` | GET | LLM 서버 상태 포함 딥 헬스체크 |
| `/v1/models` | GET | 모델 역할 목록 (`config/models.yaml`의 모든 role) |
| `/v1/chat` | POST | SSE 스트리밍 채팅 |

### ChatRequest 스키마

```json
{
  "query": "string (필수)",
  "session_id": "string (필수)",
  "user_depts": ["string (필수, 최소 1개)"],
  "history": [{"role": "user", "content": "..."}],
  "summary": "string (선택)",
  "user_id": "string (선택, LangFuse 트레이싱용)",
  "user_position": "string (선택)",
  "excluded_docs": ["string (선택, 제외할 문서 content-id)"]
}
```

검증 규칙 (위반 시 422 반환):

- `query`, `session_id`은 공백일 수 없음
- `user_depts`는 빈 배열일 수 없고, 각 항목도 공백일 수 없음

`user_depts`와 `excluded_docs`는 RAG 검색 요청 body에 그대로 전달되어 부서 권한 필터링과 문서 제외에 사용됩니다.

### SSE 이벤트 타입

| Event | Description | Data 형식 |
|-------|-------------|----------|
| `thought` | 중간 사고 과정 (`INCLUDE_THOUGHTS_IN_RESPONSE=true`일 때만 전송) | `{"content": "..."}` |
| `message` | 최종 응답 토큰 | `{"content": "..."}` |
| `error` | 에러 발생 | `{"code": "AGTxxxx", "msg": "..."}` |
| `done` | 스트림 종료 | `{"code": "...", "msg": "...", "response": "...", "sources": [...], "usage": {...}}` |

`done` 이벤트 payload:

```json
{
  "code": "AGT0000",
  "msg": "성공",
  "response": "스트리밍된 최종 답변 정본",
  "sources": [
    {"doc_id": "...", "doc_title": "...", "doc_content": "...", "location": "..."}
  ],
  "usage": {
    "input_tokens": 1234,
    "output_tokens": 567,
    "total_tokens": 1801
  }
}
```

- **`response`**: `message` 이벤트로 흘려보낸 토큰의 최종 정본. 클라이언트가 스트림을 놓쳤을 때 대조용으로 사용합니다.
- **`usage`**: rewriter / router / synthesizer 전 노드의 LLM 토큰 사용량 합산값.
- **에러 발생 시에도** `done`은 전송되며, `sources`는 빈 배열, `response`는 그때까지 스트리밍된 부분 답변, `usage`는 부분 누적값이 담깁니다.

### 검색 실패 고지 (rag 경로 한정)

`rag` 경로에서 문서 검색 결과가 0건이거나 검색이 실패하면, 답변 토큰에 **앞서** 고지 문구를 `message` 이벤트로 먼저 전송합니다. 이 문구는 `done.response`에도 합산되어 포함됩니다.

| 검색 상태 | 고지 문구 |
|----------|----------|
| `empty` (0건) | 사내 문서에서 관련 내용을 찾지 못해 일반 지식 수준에서 답변드립니다. |
| `error` (검색 실패) | 문서 검색 중 오류가 발생하여 일반 지식 수준에서 답변드립니다. |

> Mock RAG 클라이언트에서는 질문에 `검색결과없음` 문자열을 포함시키면 0건 경로를 강제로 실행할 수 있습니다.

## 5. 프로젝트 구조

```
agent/
├── main.py                          # FastAPI 앱 엔트리포인트 (로깅/트레이싱/프롬프트 prefetch)
├── pyproject.toml                   # 의존성 및 빌드 설정
├── config/
│   ├── models.yaml                  # 운영 모델 역할 설정
│   ├── models.dev.yaml              # 개발 모델 역할 설정
│   ├── models.test.yaml             # 로컬 테스트 모델 설정 (Ollama)
│   └── prompts.yaml                 # LangFuse 프롬프트 메타데이터 (이름/변수/타입)
├── prompts/
│   └── fallback/                    # CI에서 생성되는 프롬프트 fallback JSON
├── scripts/
│   ├── validate_prompts.py          # LangFuse 프롬프트 검증 + fallback JSON 생성
│   └── test_langfuse_connection.py  # LangFuse 연결 확인
├── app/
│   ├── api/v1/                      # REST API 엔드포인트
│   │   ├── chat.py                  #   POST /v1/chat (SSE 스트리밍)
│   │   ├── health.py                #   GET /health
│   │   └── models.py                #   GET /v1/models
│   ├── clients/                     # 외부 서비스 클라이언트
│   │   ├── rag_client.py            #   RAG Server 클라이언트 (Mock + Real)
│   │   └── tool_client.py           #   Tool Server 클라이언트 (Mock + Real)
│   ├── core/                        # 핵심 인프라
│   │   ├── config.py                #   pydantic-settings 설정 + models.yaml 로더
│   │   ├── enums.py                 #   에러 코드 열거형
│   │   ├── exceptions.py            #   커스텀 예외 클래스
│   │   ├── handlers.py              #   전역 예외 핸들러
│   │   ├── health.py                #   헬스체크 로직
│   │   ├── llm_factory.py           #   LLM 팩토리 (Role 라우팅 + Failover)
│   │   ├── logging_config.py        #   structlog 설정 (ADR-004)
│   │   ├── middleware.py            #   request_id + Access Log 미들웨어
│   │   ├── prompt_manager.py        #   LangFuse 프롬프트 관리 + 3단계 fallback
│   │   ├── schemas/                 #   공통 응답 스키마
│   │   └── tracing.py               #   LangFuse 트레이싱 매니저
│   └── workflows/
│       ├── main_agent/              # LangGraph 메인 워크플로우
│       │   ├── graph.py             #   그래프 빌드 + 컴파일
│       │   ├── state.py             #   AgentState 정의
│       │   ├── nodes/               #   워크플로우 노드
│       │   │   ├── rewriter.py      #     질문 재구성
│       │   │   ├── router.py        #     의도 분류 (rag/tool/both/direct)
│       │   │   ├── retriever.py     #     RAG 검색
│       │   │   ├── tool_executor.py #     도구 실행
│       │   │   └── synthesizer.py   #     최종 답변 생성
│       │   └── prompts/             #   프롬프트 빌더 (LangFuse fetch + fallback)
│       └── shared/
│           └── tracing_utils.py     #   Cross-service 트레이싱 유틸
├── tests/                           # 테스트
├── Dockerfile                       # 컨테이너 빌드
├── docker-compose.yml               # 운영(prod) 배포 설정
├── docker-compose.dev.yml           # 개발(dev) 배포 설정
├── docker-compose.langfuse.yml      # LangFuse V3 로컬 개발 환경
└── Jenkinsfile                      # CI/CD 파이프라인
```

## 6. 워크플로우

### 6.1 LangGraph 그래프

```
START → rewriter → router ─┬─ (rag)    → retriever ──────────────→ synthesizer → END
                            ├─ (tool)   → tool_executor ──────────→ synthesizer → END
                            ├─ (both)   → retriever ∥ tool_executor → synthesizer → END
                            └─ (direct) ────────────────────────────→ synthesizer → END
```

`both`는 fan-out으로 retriever와 tool_executor를 병렬 실행하고, `AgentState`의 `operator.add` reducer가 결과를 자동 병합합니다.

### 6.2 노드 설명

| Node | 역할 | 사용 모델 role | 스킵 가능 |
|------|------|---------------|----------|
| **rewriter** | 대화 맥락을 반영해 질문을 재구성 | `primary` | `SKIP_REWRITER=true` |
| **router** | 의도 분류: `rag` / `tool` / `both` / `direct` | `fast` | — |
| **retriever** | RAG Server에서 관련 문서 검색 | — | `SKIP_RAG=true` |
| **tool_executor** | Tool Server에서 도구 실행 | — | `SKIP_TOOL=true` |
| **synthesizer** | 검색 결과 + 도구 결과를 종합해 최종 답변 생성 | `primary` | — |

retriever는 RAG 호출 실패 시 예외를 전파하지 않고 `retrieval_status="error"`로 기록한 뒤 워크플로우를 계속 진행합니다 (graceful degradation).

### 6.3 워크플로우 스킵 플래그

`SKIP_RAG` / `SKIP_TOOL` / `SKIP_DIRECT` 조합이 router가 선택할 수 있는 **가용 경로**를 동적으로 제한합니다. 가용 경로가 1개 이하이면 LLM 호출 없이 해당 경로로 바로 진행합니다.

| `SKIP_RAG` | `SKIP_TOOL` | `SKIP_DIRECT` | 가용 경로 |
|:---:|:---:|:---:|-----------|
| false | false | false | `rag`, `tool`, `both`, `direct` |
| false | false | true (기본값) | `rag`, `tool`, `both` |
| false | true | true | `rag` |
| true | false | true | `tool` |

- `SKIP_REWRITER=true` → rewriter 노드를 건너뛰고 원본 query를 그대로 사용
- `SKIP_RAG=true` → retriever 노드가 `retrieval_status="skipped"`를 반환하고 context 없이 진행
- `SKIP_DIRECT=true` (기본값) → direct 경로 비활성. 모든 질문이 RAG를 경유

### 6.4 프롬프트 관리 (LangFuse)

프롬프트는 코드 배포 없이 LangFuse에서 수정할 수 있습니다. `config/prompts.yaml`에 프롬프트 이름·기대 변수·타입을 등록하면 `prompt_manager`가 이를 참조합니다.

등록된 프롬프트: `rewriter`, `router`, `synthesizer`, `synthesizer-no-rag`

**3단계 fallback 체인** — 앞 단계가 실패하면 다음 단계로 자동 전환됩니다.

1. **LangFuse fetch** (라벨 `production`, SDK 캐시 TTL `LANGFUSE_PROMPT_CACHE_TTL`)
2. **fallback JSON** (`prompts/fallback/{name}.json`, CI에서 생성)
3. **코드 하드코딩 프롬프트** (각 `prompts/*.py`의 `_FALLBACK_SYSTEM_PROMPT`)

환경 분리는 LangFuse 프로젝트(API 키)로 처리하므로 라벨은 항상 `production`을 사용합니다. 앱 시작 시 `prefetch_all()`로 전체 프롬프트를 미리 캐시에 적재합니다.

검증 및 fallback JSON 생성:

```bash
# 검증만
uv run python scripts/validate_prompts.py

# 검증 + fallback JSON 생성 (Jenkins의 Validate Prompts 단계와 동일)
uv run python scripts/validate_prompts.py --label production --generate-fallback
```

`LANGFUSE_PROMPT_ENABLED=false`이면 LangFuse API를 호출하지 않고 2·3순위 fallback만 사용합니다.

## 7. 환경변수

### 환경 / 서버

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `APP_ENV` | 환경 구분 (`dev`, `prod`, `test`). `.env.{APP_ENV}` 파일을 로드 | `dev` |
| `HOST` | 서버 바인드 주소 | `0.0.0.0` |
| `PORT` | 서버 포트 | `8000` |
| `APP_VERSION` | 앱 버전 | `1.0.0` |

### 로깅 (ADR-004)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `LOG_LEVEL` | 로깅 레벨 (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `LOG_JSON_FORMAT` | `true`: JSON 출력 + 파일 저장 (운영) / `false`: 컬러 텍스트 (개발) | `false` |
| `LOG_APP_NAME` | 서비스 이름 (로그 파일명에 사용) | `agent` |
| `LOG_DIR` | 로그 파일 저장 디렉토리 | `/app/logs` |
| `LOG_RETENTION_DAYS` | 로그 보관 기간 (일) | `14` |

### LLM

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `PRIMARY_LLM_BASE_URL` | 주 LLM 서버 URL (OpenAI-compatible) | `http://localhost:4000/v1` |
| `SECONDARY_LLM_BASE_URL` | 백업 LLM 서버 URL (Failover) | `http://localhost:4001/v1` |
| `LLM_API_KEY` | LLM API 키 | `not-needed` |
| `LLM_TIMEOUT` | LLM 요청 타임아웃 (초) | `10.0` |
| `LLM_MAX_TOKENS` | LLM 응답 최대 토큰 수 | `2048` |
| `LLM_TEMPERATURE` | 생성 temperature (0.0 ~ 2.0) | `0.6` |
| `HEALTH_CHECK_TIMEOUT` | 헬스체크 타임아웃 (초) | `5.0` |

### RAG

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `USE_MOCK_RAG` | Mock RAG 클라이언트 사용 여부 | `true` |
| `RAG_BASE_URL` | RAG Server URL | `http://localhost:8006` |
| `RAG_TIMEOUT` | RAG 요청 타임아웃 (초) | `10.0` |

### Tool

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `USE_MOCK_TOOL` | Mock Tool 클라이언트 사용 여부 | `true` |
| `TOOL_BASE_URL` | Tool Server URL | `http://localhost:8007` |
| `TOOL_TIMEOUT` | Tool 요청 타임아웃 (초) | `30.0` |

### 워크플로우

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `SKIP_REWRITER` | 질문 재구성 건너뛰기 | `false` |
| `SKIP_RAG` | RAG 검색 건너뛰기 | `false` |
| `SKIP_TOOL` | Tool 실행 건너뛰기 | `false` |
| `SKIP_DIRECT` | direct 경로 비활성 (모든 질문 RAG 경유) | `true` |
| `INCLUDE_THOUGHTS_IN_RESPONSE` | SSE thought 이벤트 포함 여부 | `false` |
| `MODEL_CONFIG_PATH` | 모델 역할 설정 파일 경로 | `config/models.yaml` |

### LangFuse

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `LANGFUSE_TRACING_ENABLED` | 트레이싱 활성화 여부 | `true` |
| `LANGFUSE_PUBLIC_KEY` | LangFuse Public Key | — |
| `LANGFUSE_SECRET_KEY` | LangFuse Secret Key | — |
| `LANGFUSE_HOST` | LangFuse 서버 URL | `https://cloud.langfuse.com` |
| `LANGFUSE_PROMPT_ENABLED` | 프롬프트 관리 활성화 여부 | `true` |
| `LANGFUSE_PROMPT_CACHE_TTL` | 프롬프트 캐시 TTL (초) | `300` |
| `LANGFUSE_PROMPT_CONFIG_PATH` | 프롬프트 메타데이터 파일 경로 | `config/prompts.yaml` |

> 키가 설정되어 있어도 `LANGFUSE_TRACING_ENABLED=false`이면 트레이싱이 비활성화됩니다.
> `LANGFUSE_PROMPT_ENABLED`는 트레이싱이 활성화된 경우에만 유효합니다 (키 미설정 시 자동 비활성).

## 8. 배포/운영

### Docker 빌드

```bash
docker build -t agent .
```

- **베이스 이미지**: `python:3.11-slim`
- **의존성 설치**: `uv sync --frozen --extra tracing --no-dev` (uv.lock 기반 버전 고정, LangFuse 포함)
- **헬스체크**: 30초 간격, `curl -f http://localhost:8000/health`
- **포트**: 8000

### docker-compose

| 파일 | 용도 | 이미지 태그 | 컨테이너 | 기본 포트 |
|------|------|------------|---------|----------|
| `docker-compose.yml` | 운영(prod) 배포 | `:latest` | `agent` | `8000` |
| `docker-compose.dev.yml` | 개발(dev) 배포 | `:dev-latest` | `agent-dev` | `8500` |
| `docker-compose.langfuse.yml` | LangFuse V3 로컬 환경 | — | — | `3000` |

```bash
# 운영
docker compose -p agent up -d

# 개발
docker compose -p agent-dev -f docker-compose.dev.yml up -d
```

공통 설정: `.env` 파일 마운트, `./logs:/app/logs` 볼륨, `/health` 헬스체크(30초 간격), `json-file` 로그 로테이션(max 10MB × 10개), `unless-stopped` 재시작 정책.

### Jenkins CI/CD 파이프라인

```
Checkout → Docker Build → Validate Prompts → Docker Push → Deploy
```

1. **Checkout**: 소스 체크아웃 후 브랜치로 환경 결정 (`main` → prod, 그 외 → dev)
2. **Docker Build**: 이미지 빌드 (빌드 번호 + `latest` / `dev-latest` 태그)
3. **Validate Prompts**: 빌드된 이미지로 `validate_prompts.py --label production --generate-fallback` 실행. LangFuse에 프롬프트가 없거나 변수가 불일치하면 배포를 중단합니다.
4. **Docker Push**: 사내 레지스트리(`registry.example.com`)에 이미지 Push
5. **Deploy**: SSH로 배포 서버에 `.env` + compose 파일을 전송하고 `docker compose pull && up -d`

브랜치별 배포 대상:

| 브랜치 | 환경 | compose 파일 | compose 프로젝트 | 배포 경로 |
|--------|------|-------------|-----------------|----------|
| `main` | prod | `docker-compose.yml` | `agent` | `/home/ubuntu/agent/compose` |
| 그 외 | dev | `docker-compose.dev.yml` | `agent-dev` | `/home/ubuntu/agent-dev/compose` |

### LangFuse 로컬 개발 환경

```bash
docker compose -f docker-compose.langfuse.yml up -d
```

LangFuse V3 + PostgreSQL + ClickHouse + Redis + MinIO를 로컬에 구성합니다.
초기 설정: `http://localhost:3000` 접속 → 회원가입 → 프로젝트 생성 → API Keys 복사 → `.env.dev`에 설정

## 9. 개발 가이드

### 커스터마이징

- **LLM 모델 변경**: `config/models.yaml`에서 역할별 모델명을 수정 → [모델 설정 가이드](wiki/guides/model-configuration.md)
- **워크플로우 노드 추가**: `app/workflows/main_agent/nodes/`에 노드 생성 후 `graph.py`에 등록 → [노드 추가 가이드](wiki/guides/add-workflow-node.md)
- **프롬프트 수정**: LangFuse UI에서 편집 (권장) 또는 `app/workflows/main_agent/prompts/`의 하드코딩 fallback 수정. 새 프롬프트는 `config/prompts.yaml`에 등록 필요

### 테스트

총 **441개** 테스트 (단위 408 + 통합 33). 상세 목록은 [테스트 문서](wiki/tests.md)를 참조하세요.

#### 단위 테스트

```bash
# 전체 실행 (통합 테스트 자동 제외)
uv run pytest

# 상세 출력
uv run pytest -v

# 특정 파일
uv run pytest tests/test_chat.py -v

# 특정 클래스
uv run pytest tests/test_chat.py::TestChatRequestSchema -v

# 특정 테스트
uv run pytest tests/test_chat.py::TestFormatSSE::test_format_sse_thought -v

# 커버리지 포함
uv run pytest --cov=app --cov-report=term-missing

# HTML 커버리지 리포트
uv run pytest --cov=app --cov-report=html
# → htmlcov/index.html 에서 확인
```

#### 통합 테스트

실제 LLM 서버, LangFuse, RAG/Tool 서버가 필요합니다. 서버가 없으면 자동으로 스킵됩니다.

```bash
# 통합 테스트 실행
uv run pytest tests/integration/ -m integration -v

# tox로 실행
tox -e integration
```

| 테스트 파일 | 필요 서버 | 대상 |
|------------|----------|------|
| test_chat_integration.py | LLM | Chat API E2E |
| test_langfuse_integration.py | LLM, LangFuse | 트레이싱 + Cross-service 헤더 |
| test_prompt_management.py | LangFuse | 프롬프트 fetch + fallback 체인 |
| test_workflow_routes.py | LLM, RAG, Tool | 워크플로우 라우트별 실행 |

#### tox

```bash
tox              # 단위 테스트
tox -e integration  # 통합 테스트
tox -e coverage  # 커버리지 리포트
tox -e lint      # 린트 검사
```

### 린트

```bash
# 검사
uv run ruff check app/ tests/

# 자동 수정
uv run ruff check app/ tests/ --fix
```

## 10. 문서

- **가이드**
  - [Ollama 설정](wiki/guides/ollama-setup.md)
  - [모델 설정](wiki/guides/model-configuration.md)
  - [워크플로우 노드 추가](wiki/guides/add-workflow-node.md)
  - [라우터 의도 분류 테스트](wiki/guides/router-testing.md)
  - [LangFuse 트레이싱 아키텍처](wiki/guides/langfuse-tracing.md)
- [테스트 문서](wiki/tests.md)

## License

Apache License 2.0. 전문은 저장소 루트의 `LICENSE`.
