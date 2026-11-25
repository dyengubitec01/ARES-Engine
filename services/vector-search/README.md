# RAG Search Server

검색 전용 Lightweight RAG 서버 — 문서 적재 없이 벡터 검색 + 리랭킹 파이프라인만 수행

## 1. 서버 개요

에이전트 시스템의 검색 백엔드로, 사용자 쿼리를 벡터로 변환하고 Qdrant에서 후보 문서를 검색한 뒤 리랭커로 정밀 순위화하여 반환하는 서버입니다.

### 파이프라인

```
query → embed (Embedding Server) → vector search (Qdrant) → rerank (Reranker Server) → response
```

### 시스템 구성도

```
                     ┌──────────────────────┐
                     │    Agent Server      │
                     └──────────┬───────────┘
                                │
                     X-LF-Trace-ID, X-LF-Parent-Id
                                │
                     ┌──────────▼───────────┐
                     │  RAG Search Server   │
                     │     (이 서버)         │
                     └──┬──────┬──────┬─────┘
                        │      │      │
            ┌───────────┘      │      └───────────┐
            ▼                  ▼                   ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
  │  Embedding   │  │   Qdrant     │  │   Reranker       │
  │   Server     │  │  Vector DB   │  │    Server        │
  │  (BGE-M3)    │  │              │  │ (bge-reranker-m3)│
  └──────────────┘  └──────────────┘  └──────────────────┘

                     ┌──────────────────────┐
                     │  LangFuse (Optional) │
                     │    Observability      │
                     └──────────────────────┘
```

### 통신 프로토콜

| 통신 경로 | 프로토콜 | 커스텀 헤더 | 설명 |
|-----------|----------|------------|------|
| Agent → RAG Search | REST (httpx) | `X-LF-Trace-ID`, `X-LF-Parent-Id` | 검색 요청 |
| RAG Search → Embedding Server | REST (httpx) | — | 쿼리 임베딩 변환 (BGE-M3) |
| RAG Search → Qdrant | REST (qdrant-client) | — | 벡터 유사도 검색 |
| RAG Search → Reranker | REST (httpx) | — | 결과 정밀 순위화 |
| RAG Search → LangFuse | REST (SDK) | — | 트레이싱 데이터 전송 |

## 2. 기술 스택

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.11+ |
| Web Framework | FastAPI | >=0.104.0 |
| Validation | Pydantic v2 + pydantic-settings | >=2.0 |
| HTTP Client | httpx | >=0.25.0 |
| Vector DB Client | qdrant-client | >=1.12.0 |
| Tracing (optional) | Langfuse SDK v3 | >=3.8.0 |
| Containerization | Docker | python:3.11-slim |
| CI/CD | Jenkins | Declarative Pipeline |

## 3. 빠른 시작

### Prerequisites

- Python 3.11+

### Installation

```bash
# Clone repository
git clone <repository-url>
cd RAG-Search

# 가상환경 생성 + 의존성 설치
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 환경변수 설정 (APP_ENV 값에 따라 .env.{APP_ENV} 가 자동 로드됨)
cp .env.example .env.dev
```

### Configuration

`.env.dev`(개발) 또는 `.env.prod`(운영) 파일을 환경에 맞게 설정합니다. `APP_ENV` 값에 따라 `.env.{APP_ENV}` 파일이 자동 로드됩니다.

```bash
# 개발 환경 (.env.dev 로드)
APP_ENV=dev          # .env.dev 파일을 로드. 어댑터는 실제 Qdrant/BGE-M3/Reranker에 연결
LOG_LEVEL=DEBUG
```

> `APP_ENV` 값은 로드할 `.env.{APP_ENV}` 파일만 결정합니다. **어댑터는 환경과 무관하게 항상 실제 어댑터가 주입되므로**, 서버를 기동하려면 Qdrant·임베딩·리랭커가 접근 가능해야 합니다. 외부 시스템 없이 검증하려면 Mock 어댑터를 주입하는 단위 테스트(`pytest`)를 사용하세요. (`prod`에서는 에러 응답의 상세 메시지가 숨겨집니다.)

운영 환경에서는 실제 서버 URL을 설정합니다:

```bash
APP_ENV=prod
QDRANT_URL=http://your-qdrant:6333
EMBEDDING_API_URL=http://your-embedding-server:8100/query
RERANKER_URL=http://your-reranker:8011/rerank
```

> 전체 환경변수 목록은 [7. 환경변수](#7-환경변수) 참조

### Running

```bash
# 개발 서버 (hot-reload)
uvicorn app.main:app --reload

# 프로덕션
uvicorn app.main:app --host 0.0.0.0 --port 8006
```

## 4. API 엔드포인트

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | 헬스체크 |
| `/v1/search` | POST | 벡터 검색 + 리랭킹 |

### SearchRequest 스키마

```json
{
  "query": "검색할 텍스트 (필수)",
  "user_depts": ["dept-uuid-1", "dept-uuid-2"],
  "excluded_docs": ["doc-content-id-1"],
  "top_k": 6,
  "search_k": 20
}
```

- `query`: **필수**. 빈 문자열 불가.
- `user_depts`: **필수**. 부서 UUID 리스트(빈 리스트 불가). 단, **검색 필터에는 사용하지 않으며**(전 부서 검색 개방) 로깅·모니터링 목적으로만 전달된다.
- `excluded_docs`: 선택(기본값 `[]`). 검색에서 제외할 `doc_content_id` 리스트.
- `top_k`: 선택. 리랭킹 후 남길 **시드 청크 수**. 미지정(`null`)이면 Settings.TOP_K = 6.
- `search_k`: 선택. 1차 벡터 검색 후보 수. 미지정(`null`)이면 Settings.SEARCH_K = 20.

> 다음 경우 `RAG100020`(400)이 반환된다: 빈 `query`, 빈 `user_depts`, `top_k` 또는 `search_k` ≤ 0.

> **응답 건수와 `top_k`의 관계**: `PARENT_EXPANSION_ENABLED=false`(기본)이면 응답은 정확히 `top_k`개 청크다.
> 확장이 켜져 있으면 각 시드 청크가 속한 parent와 인접 parent(N-1·N·N+1)로 확장·병합되므로,
> 응답은 청크가 아니라 **parent 단위**가 되고 건수는 시드 수와 달라진다(문서 단위 dedup 후 최대 `3 × top_k` parent).
> 즉 확장 ON일 때 `top_k`는 "최종 반환 수"가 아니라 "확장의 시드가 되는 청크 수"다.

### 성공 응답

```json
{
  "code": "RAG100000",
  "msg": "검색 성공",
  "data": {
    "query": "검색 쿼리",
    "trace_id": "a1b2c3d4...",
    "results": [
      {
        "rank": 1,
        "score": 0.92,
        "content": "문서 본문 텍스트...",
        "metadata": {
          "doc_id": "doc-0001",
          "original_filename": "report.pdf",
          "location_context": "페이지 3-4"
        }
      }
    ]
  }
}
```

- `results[].metadata`에는 `doc_id`(payload의 `doc_content_id`에서 매핑), `original_filename`, `location_context`만 포함된다. payload에 존재하는 값만 실리므로, 해당 필드가 없는 청크는 키 자체가 생략된다.
- 확장(`PARENT_EXPANSION_ENABLED=true`) 시 `content`는 병합된 parent 전체 본문이고 `rank`/`score`는 parent 단위로 부여된다.

### 결과 없음 응답

```json
{
  "code": "RAG100001",
  "msg": "검색 결과 없음"
}
```

### 에러 응답

```json
{
  "code": "RAG100020",
  "msg": "잘못된 요청"
}
```

### 트레이싱 헤더

| 헤더 | 방향 | 필수 | 설명 |
|------|------|------|------|
| `X-LF-Trace-ID` | 요청 | 선택 | 클라이언트가 전달하면 해당 trace에 연결. 없으면 서버에서 생성 |
| `X-LF-Parent-Id` | 요청 | 선택 | 부모 span ID. child span 연결용 |
| `X-LF-Trace-ID` | 응답 | 항상 | 사용된 trace ID를 응답 헤더에 포함 |

### Fallback 동작

리랭커 장애 시 1차 벡터 검색 결과를 그대로 반환합니다. 이 경우 응답 data에 `"fallback": true` 필드가 추가됩니다:

```json
{
  "code": "RAG100000",
  "msg": "검색 성공",
  "data": {
    "query": "검색 쿼리",
    "trace_id": "a1b2c3d4...",
    "results": [...],
    "fallback": true
  }
}
```

### 에러 코드

| Code | Name | HTTP Status | 설명 |
|------|------|-------------|------|
| `RAG100000` | SEARCH_SUCCESS | 200 | 검색 성공 |
| `RAG100001` | NO_RESULT | 200 | 검색 결과 없음 |
| `RAG100020` | BAD_REQUEST | 400 | 잘못된 요청 |
| `RAG100040` | EMBEDDING_FAILURE | 502 | 임베딩 연동 실패 |
| `RAG100050` | RERANKER_FAILURE | 502 | 리랭커 연동 실패 |
| `RAG100060` | VECTOR_STORE_FAILURE | 502 | 벡터 스토어 연동 실패 |
| `RAG100099` | INTERNAL_ERROR | 500 | 서버 내부 오류 |

코드 형식: `RAG` + 6자리 숫자 `[Major 2자리][Middle 2자리][Minor 2자리]`

## 5. 프로젝트 구조

```
RAG-Search/
├── app/
│   ├── api/                         # API 계층
│   │   ├── routes.py                #   POST /v1/search (query, user_depts, excluded_docs, top_k, search_k)
│   │   └── responses.py             #   RAGCode, APIResponse, 응답 헬퍼
│   ├── core/                        # 핵심 인프라
│   │   ├── config.py                #   pydantic-settings 환경 설정
│   │   ├── exceptions.py            #   커스텀 예외 클래스
│   │   ├── interfaces.py            #   ABC 인터페이스 (Embedding, VectorStore, Reranker)
│   │   ├── monitoring.py            #   LangfuseMiddleware + observe + safe_update_span
│   │   └── payload_fields.py        #   Qdrant payload 필드 Enum
│   ├── services/                    # 비즈니스 로직
│   │   └── search_service.py        #   검색 파이프라인 오케스트레이터 (RRF 합산 + parent ±1 확장)
│   ├── adapters/                    # 외부 시스템 어댑터
│   │   ├── embedding_adapter.py     #   BGE-M3 임베딩 API
│   │   ├── qdrant_adapter.py        #   Qdrant dense/full-text 검색 + parent 청크 회수
│   │   ├── reranker_adapter.py      #   bge-reranker-v2-m3 리랭커
│   │   └── mocks/                   #   테스트 전용 Mock 어댑터 (conftest.py 주입)
│   │       ├── mock_embedding.py
│   │       ├── mock_vector_store.py
│   │       └── mock_reranker.py
│   └── main.py                      # FastAPI 앱 팩토리, 글로벌 예외 핸들러
├── tests/                           # 단위·통합 테스트 (pytest)
├── scripts/
│   └── create_fulltext_index.sh     # Qdrant full-text index 생성 (Hybrid Search 사전작업)
├── wiki/
│   └── tests.md                     # 테스트 인벤토리 문서
├── Dockerfile                       # 컨테이너 빌드
├── docker-compose.yml               # 운영 배포 설정
├── docker-compose.dev.yml           # 개발용 Docker Compose
├── Jenkinsfile                      # CI/CD 파이프라인
├── pyproject.toml                   # 의존성 및 빌드 설정
└── .env.example                     # 환경변수 템플릿 (.env.dev / .env.prod 로 복사)
```

## 6. 검색 파이프라인

### 파이프라인 흐름

```
[Client Request]
       │
       ▼
┌─────────────────────┐
│ LangfuseMiddleware  │  trace-id 할당/승계, root span 생성
└──────────┬──────────┘
           ▼
┌───────────────────────────────────────────────┐
│                SearchService                  │
├───────────────────────────────────────────────┤
│ 1. embed()                                    │  query → BGE-M3 → vector
│ 2. retrieve()                                 │
│    ├─ (OFF) vector_store.search()             │  dense only → candidates
│    └─ (ON)  _retrieve_hybrid()                │
│             ├─ dense + BM25 asyncio.gather    │
│             ├─ RRF 합산 (key=_point_id)       │
│             └─ 상위 search_k개 절삭           │
│ 3. rerank()                                   │  candidates → Reranker → top_k
│    └─ fallback                                │  리랭커 장애 시 candidates[:top_k] 반환
│ 4. build_results()                            │  score_threshold + metadata 필터링
│    ├─ (OFF) 청크 단위 결과                     │  매칭 청크 top_k개 그대로 반환
│    └─ (ON)  _expand_to_parents()              │  parent ±1 회수·병합·재정렬 (최대 3×top_k parent)
└──────────┬────────────────────────────────────┘
           ▼
     [Response]
```

### 단계별 설명

| 단계 | 어댑터 | 입력 | 출력 |
|------|--------|------|------|
| **Embedding** | EmbeddingAdapter → Embedding Server | query (str) | vector (list[float], 1024dim) |
| **Dense Search** | QdrantAdapter.search | vector, search_k | candidates (content + metadata + score + _point_id) |
| **Keyword Search** (hybrid ON) | QdrantAdapter.text_search | query_text, search_k | candidates (Qdrant full-text 토큰 매칭 결과) |
| **RRF Fusion** (hybrid ON) | SearchService._rrf_fuse | dense + keyword | 합산 정렬 후 search_k개 |
| **Reranking** | RerankerAdapter | query, texts, top_k | reranked (index + score + text) |
| **Parent Expansion** (flag ON) | QdrantAdapter.fetch_chunks_by_parents | reranked 청크의 (doc_content_id, parent_id) | parent N-1·N·N+1 청크를 chunk_index 순으로 병합한 result |
| **Fallback** | — | candidates[:top_k] | 리랭커 장애 시 1차 결과 반환 (원본 score 유지) |

### Hybrid 실패 매트릭스

| Dense | BM25 | 결과 |
|-------|------|------|
| ✓ | ✓ | RRF 합산 → Reranker |
| ✓ | ✗ | WARN 로그, dense-only로 진행 |
| ✗ | ✓ | WARN 로그, BM25-only로 진행 |
| ✗ | ✗ | `VectorStoreException` 전파 → 502 |

### Langfuse Span 구조

Langfuse가 활성화된 경우, 요청당 다음 span 계층이 기록됩니다:

```
rag-search (root span, middleware)
├── embedding              (as_type: embedding)
├── vector-search          (as_type: retriever)
│   └── (hybrid 모드일 때)
│       ├── dense-search   (as_type: retriever)
│       ├── bm25-search    (as_type: retriever)
│       └── rrf-fusion     (as_type: span)
├── reranking              (as_type: span)
└── parent-expansion       (as_type: span, PARENT_EXPANSION_ENABLED + parent_id 존재 시)
```

- `X-LF-Trace-ID` 헤더가 있으면 해당 trace에 연결 (cross-service 전파)
- `X-LF-Parent-Id` 헤더가 있으면 해당 span의 child로 연결
- 헤더가 없으면 서버에서 trace-id를 새로 생성하지만, Langfuse trace는 생성하지 않음
- `vector-search` span input의 `search_mode` 필드로 `hybrid` / `dense_only` 구분
- `parent-expansion` span은 `PARENT_EXPANSION_ENABLED=true`이고 매칭 청크에 `parent_id`가 있을 때만 기록된다 (root span 직속, `doc_count` / `fetched_chunks` / `parent_count` 출력)

## 7. 환경변수

### App

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `APP_ENV` | 로드할 `.env.{APP_ENV}` 파일 선택 (어댑터는 항상 실제). `prod`은 에러 상세 숨김 | `dev` |
| `APP_HOST` | 서버 바인드 주소 | `0.0.0.0` |
| `APP_PORT` | 서버 포트 | `8006` |
| `LOG_LEVEL` | 로깅 레벨 (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `DEBUG` |

### Qdrant

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `QDRANT_URL` | Qdrant 서버 URL | `http://localhost:6333` |
| `QDRANT_COLLECTION` | 컬렉션 이름 | `documents` |
| `QDRANT_CONTENT_FIELD` | payload에서 본문 텍스트 필드명 | `text_for_search` |

### Embedding

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `EMBEDDING_API_URL` | BGE-M3 임베딩 API URL | `http://localhost:8100/query` |

### Reranker

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `RERANKER_URL` | bge-reranker-v2-m3 API URL | `http://localhost:8011/rerank` |

### Langfuse

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `LANGFUSE_ENABLED` | 트레이싱 활성화 여부 | `false` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse 프로젝트 공개 키 | (빈 문자열) |
| `LANGFUSE_SECRET_KEY` | Langfuse 프로젝트 비밀 키 | (빈 문자열) |
| `LANGFUSE_HOST` | Langfuse 서버 URL | `https://cloud.langfuse.com` |

> `LANGFUSE_ENABLED=false`이면 키가 설정되어 있어도 트레이싱이 비활성화됩니다.

### Search Parameters

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `SEARCH_K` | 1차 벡터 검색 후보 수 | `20` |
| `TOP_K` | 리랭킹 후 남길 시드 청크 수 (확장 OFF 시 곧 응답 건수, ON 시 확장 시드) | `6` |
| `SCORE_THRESHOLD` | 리랭킹 score 임계값 (0.0 = 필터링 없음) | `0.0` |

### Hybrid Search (Dense + Keyword)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `HYBRID_SEARCH_ENABLED` | Dense + 키워드 하이브리드 검색 활성화 | `false` |
| `RRF_K` | Reciprocal Rank Fusion 상수 (표준 60) | `60` |

> `HYBRID_SEARCH_ENABLED=true`로 켜려면 **반드시** Qdrant 컬렉션에
> full-text index가 선행 생성되어 있어야 합니다. 자세한 절차는
> [§8. 배포/운영 — Hybrid Search 운영 가이드](#hybrid-search-운영-가이드)를
> 참고하세요.
>
> 키워드 검색은 Qdrant full-text payload index(`MatchText`) 기반이며
> 정규 BM25 scoring이 아닙니다. 리랭커가 최종 순위를 교정하므로 1차
> 후보 수집 목적엔 충분하며, 재임베딩/재적재 없이 인덱스만 추가하면
> 되는 점이 채택 이유입니다. 진짜 BM25 scoring이 필요해지면 Qdrant
> sparse vector(fastembed) 또는 BGE-M3 learned sparse로 업그레이드
> 가능하나 재적재가 필요합니다.

### Parent-document Expansion (실험적)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `PARENT_EXPANSION_ENABLED` | 리랭킹된 청크를 parent ±1 단위로 통째 회수·병합 | `false` |

> `true`이면 리랭킹 결과의 각 청크에 대해 같은 문서(`doc_content_id`)의
> `parent_id` N-1·N·N+1 청크를 모두 회수하여 `chunk_index` 순으로 병합한 뒤
> 대표 score로 재정렬한다. `parent_id`가 없는 청크는 단일 result로 통과시킨다
> (혼재 컬렉션 방어). 확장 단계에서 오류가 나면 기본 청크 결과로 안전하게
> 폴백한다. Qdrant payload에 `doc_content_id` / `parent_id` / `chunk_index`
> 필드가 존재해야 효과가 있다.

### HTTP Client

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `HTTP_TIMEOUT` | 외부 API 호출 타임아웃 (초) | `30.0` |

## 8. 배포/운영

### Docker 빌드

```bash
docker build -t rag-search .
```

- **베이스 이미지**: `python:3.11-slim`
- **레이어 캐싱**: `pyproject.toml` 먼저 복사 → `pip install` → 소스 복사
- **헬스체크**: 30초 간격, `curl -f http://localhost:8006/health`
- **포트**: 8006

### docker-compose.yml (운영)

```bash
docker compose up -d
```

| 항목 | 설정 |
|------|------|
| 이미지 | `registry.example.com/ares/rag-search:latest` |
| 포트 | `8006:8006` |
| 환경변수 | `.env` 파일 마운트 |
| 볼륨 | `./logs:/app/logs` (로그 파일) |
| 헬스체크 | 30초 간격, `/health` 엔드포인트 |
| 로그 로테이션 | `json-file`, max 10MB x 10개 |
| 재시작 정책 | `unless-stopped` |

### Jenkins CI/CD 파이프라인

```
Checkout → Docker Build → Docker Push → Deploy
```

1. **Checkout**: 소스 코드 체크아웃
2. **Docker Build**: 이미지 빌드 (빌드 번호 + latest 태그)
3. **Docker Push**: 사내 레지스트리(`registry.example.com`)에 Push
4. **Deploy**: SSH로 배포 서버(`localhost`)에 `docker compose pull && up -d`

### Hybrid Search 운영 가이드

Hybrid Search(Dense + 키워드 필터)를 사용하려면 Qdrant 컬렉션의
`text_for_search` 필드에 **full-text payload index**를 1회 생성해야 한다.
앱은 인덱스를 생성하지 않는다(검색 전용 원칙). 운영자가 수동으로 수행한다.

> 현 구현은 Qdrant `MatchText` 기반 토큰 매칭이며 정규 BM25 scoring이 아니다.
> 재임베딩 회피를 위해 채택됐고, 리랭커가 최종 순위를 교정한다.

#### 신규 Qdrant 컬렉션 체크리스트

새 컬렉션(`rag_chunks_v*_dev`, `rag_chunks_v*` 등)을 적재할 때마다 다음 순서로 수행한다:

1. 적재 파이프라인이 컬렉션 생성 + 벡터 데이터 업로드 완료
2. **`scripts/create_fulltext_index.sh` 실행** 으로 `text_for_search` full-text index 생성 (권장, 1회성)
   - 또는 아래 curl/Python 스니펫 중 하나를 수동 실행
3. dev 컬렉션에서 [한국어 Smoke Test](#한국어-smoke-test) 5개 쿼리 통과 확인
4. prod 컬렉션에도 동일하게 스크립트 실행
5. `.env.prod`에 `HYBRID_SEARCH_ENABLED=true` 설정 후 컨테이너 재시작
6. 앱 로그에 `Hybrid Search 비활성화` ERROR가 없는지 확인 (있으면 인덱스 누락)
7. Langfuse trace에서 `vector-search` span input의 `search_mode=hybrid` 확인

#### Full-Text Index 생성 — 스크립트 (권장)

```bash
# prod 기본값으로 실행
bash scripts/create_fulltext_index.sh

# 다른 대상으로 실행
QDRANT_URL=http://localhost:6333 COLLECTION=rag_chunks_v1_dev \
  bash scripts/create_fulltext_index.sh
```

스크립트는 인덱스 생성(PUT)과 생성 확인(GET payload_schema)을 연속 수행한다. idempotent하므로 중복 실행해도 안전하다.

#### Full-Text Index 생성 — curl

```bash
curl -X PUT "http://<qdrant-host>:6333/collections/<collection>/index" \
  -H "Content-Type: application/json" \
  -d '{
    "field_name": "text_for_search",
    "field_schema": {
      "type": "text",
      "tokenizer": "multilingual",
      "min_token_len": 2,
      "max_token_len": 20,
      "lowercase": true
    }
  }'
```

#### Full-Text Index 생성 — Python

```python
from qdrant_client import QdrantClient
from qdrant_client.models import TextIndexParams, TokenizerType, PayloadSchemaType

client = QdrantClient(url="http://<qdrant-host>:6333")
client.create_payload_index(
    collection_name="<collection>",
    field_name="text_for_search",
    field_schema=TextIndexParams(
        type=PayloadSchemaType.TEXT,
        tokenizer=TokenizerType.MULTILINGUAL,
        min_token_len=2,
        max_token_len=20,
        lowercase=True,
    ),
)
```

idempotent: 이미 같은 스키마의 인덱스가 있으면 Qdrant가 no-op 처리한다.

#### 인덱스 존재 확인 — curl

```bash
curl -s "http://<qdrant-host>:6333/collections/<collection>" \
  | python -c "import sys, json; \
      info = json.load(sys.stdin)['result']; \
      print(info.get('payload_schema', {}).get('text_for_search', 'NOT_FOUND'))"
```

앱 startup 시 자동으로 이 확인이 수행되며, 인덱스가 없으면
`HYBRID_SEARCH_ENABLED`를 런타임에 `false`로 비활성화하고 ERROR 로그를
남긴다 (서비스는 dense-only로 정상 기동).

#### 한국어 Smoke Test

인덱스 생성 후 dev 컬렉션에서 수동으로 실행한다. 각 쿼리를 `/v1/search`에
POST하여 결과를 확인하고, 특히 hybrid OFF 대비 recall 개선을 Langfuse trace
의 `dense-search` / `bm25-search` child span에서 비교한다.

| # | 쿼리 유형 | 예시 쿼리 | 기대 효과 |
|---|-----------|-----------|-----------|
| 1 | 고유명사 / 문서번호 | `KB-2024-07-15 지침서` | BM25가 dense보다 정확 매칭 |
| 2 | 영문 약어 | `HRIS 권한 설정` | BM25 히트 우세 |
| 3 | 자연어 질의 (조사 포함) | `연차 사용 규정이 어떻게 되나요` | Dense 우세, BM25 보조 |
| 4 | 숫자 코드 | `ERP 4.2.1 변경 사항` | BM25 강점 |
| 5 | 약간의 오탈자 | `휴가 신청 방법` vs `휴과 신청 방법` | multilingual tokenizer 내성 확인 |

체크 항목:
- [ ] 각 쿼리가 200 응답을 반환한다
- [ ] `search_mode=hybrid` 로 기록된다 (Langfuse)
- [ ] `rrf-fusion` span의 `overlap_count`가 1 이상이다 (양쪽 매칭 확인)
- [ ] dense-only 대비 고유명사/약어 쿼리의 결과 품질이 향상된다
- [ ] 에러 로그에 `Hybrid 검색` 관련 ERROR/WARN가 없다

## 9. 개발 가이드

### DI 패턴

앱 팩토리(`create_app`)는 환경과 무관하게 **항상 실제 어댑터**를 주입하고 `app.state.search_service`에 바인딩합니다:

| 계층 | 어댑터 |
|------|--------|
| Embedding | EmbeddingAdapter |
| VectorStore | QdrantAdapter |
| Reranker | RerankerAdapter |

Mock 어댑터(`app/adapters/mocks/`)는 **단위 테스트에서만** 사용됩니다 — `tests/conftest.py`가 별도 테스트 앱에 `MockEmbeddingAdapter` / `MockVectorStore` / `MockReranker`를 주입합니다. `APP_ENV`는 어댑터 선택에 관여하지 않으며, 로드할 `.env.{APP_ENV}` 파일 선택과 `prod`에서의 에러 상세 숨김에만 영향을 줍니다.

### 테스트

총 **226개** 테스트 (단위) + **3개** (통합, 별도 실행) = **229개**. 상세 목록은 [테스트 문서](wiki/tests.md)를 참조하세요.

#### 단위 테스트

```bash
# 전체 실행 (통합 테스트 자동 제외)
pytest

# 상세 출력
pytest -v

# 특정 파일
pytest tests/test_search.py -v

# 커버리지 포함
pytest --cov=app --cov-report=term-missing
```

#### 통합 테스트

실제 임베딩 API와 Qdrant 서버가 필요합니다. 서버가 없으면 자동으로 스킵됩니다.

```bash
# 통합 테스트 실행
pytest --run-integration -v
```

## 10. 문서

- [테스트 문서](wiki/tests.md) — 전체 테스트 인벤토리 (파일별 클래스별 상세)
