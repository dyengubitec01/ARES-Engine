# ARES Engine

ARES Engine(Autonomous Retrieval Evaluation & Optimization System) 기반 Hybrid RAG 자동 최적화 및 지능형 질의응답 시스템.
비정형 문서를 벡터 인덱스와 지식그래프로 색인하고, 골든 데이터셋으로 검색 성능을 측정해 검색 기법을 채택·기각한다.

| 항목 | 값 |
|---|---|
| 버전 | 1.0 |
| 라이선스 | Apache License 2.0 (`LICENSE`) |
| 구성 | 웹 UI · API 서버 · 채팅 에이전트 · 벡터 검색 · 그래프 검색 · 도구 서버 · 벡터 색인 · 그래프 색인 · 평가 |
| 언어 | TypeScript(웹 · API), Python(에이전트 · 검색 · 색인 · 평가) |

※ 이 저장소는 운영 버전에서 접속 정보 · 비밀값 · 사내 데이터를 제거한 공개본이다. 서버 주소 기본값은 `localhost`이고, 비밀번호 · API 키는 환경변수로 넣는다.

## 구성

| 경로 | 역할 | 주요 기술 |
|---|---|---|
| `apps/frontend` | 웹 UI: 채팅(SSE 스트리밍), 문서 업로드 · 관리, 관리자 화면 | React, Vite, TypeScript |
| `apps/backend` | API 서버: 인증, 채팅 중계, 문서 업로드(MinIO Presigned URL), 관리 기능 | NestJS, PostgreSQL, Redis, Kafka |
| `services/agent` | 채팅 에이전트: 의도 분류, 검색 · 도구 호출, 답변 생성 | LangGraph, FastAPI |
| `services/vector-search` | 벡터 검색 서버: 질의 임베딩 → Qdrant 검색 → 리랭킹 | FastAPI, Qdrant |
| `services/graph-search` | 그래프 검색 서버: 질의 개체 링킹 → 이웃 확장 → 청크 회수(독립 API `POST /v1/graph-search`) | FastAPI, PostgreSQL |
| `services/tools` | 도구 서버: 요약, 도구 관리, LLM 게이트웨이 | FastAPI |
| `index/vector-index` | 벡터 색인: 문서 텍스트 추출 · 청킹 · BGE-M3 임베딩 · Qdrant 적재 | FastAPI, Kafka, MinIO |
| `index/graph-index` | 그래프 색인: GLiNER2 개체 추출 · LLM 관계 라벨링 · Louvain 커뮤니티 · 개체 임베딩, 평가 도구 | networkx, vLLM(OpenAI 호환 API) |
| `eval/deepeval-runner` | 답변 품질 평가: LLM trace를 DeepEval 지표로 채점 | DeepEval, Langfuse |
| `eval/results` | 검색 성능 측정 결과 | — |

## 처리 흐름

```
[색인]
문서 업로드 → apps/backend → Kafka → index/vector-index(추출 · 청킹 · BGE-M3 임베딩) → Qdrant · PostgreSQL
청크 DB → index/graph-index(GLiNER2 개체 추출 · LLM 관계 라벨링 · Louvain, 야간 배치) → PostgreSQL · Qdrant(개체 벡터)

[질의]
사용자 → apps/frontend → apps/backend → services/agent ┬→ services/vector-search(벡터 검색 · 리랭킹)
                                                        ├→ services/tools(요약 · 도구)
                                                        └→ LLM(OpenAI 호환 API)
services/graph-search: 개체 그래프 기반 청크 회수(독립 API)
```

## 실행 환경

| 항목 | 내용 |
|---|---|
| 외부 서비스 | PostgreSQL, Qdrant, Kafka, MinIO, Redis, Langfuse |
| 추론 서버 | LLM(OpenAI 호환 API, 예: vLLM), BGE-M3 임베딩, GLiNER2 개체 추출 |
| 설정 | 각 모듈 폴더의 `.env.example`을 복사해 `.env`를 만들고, `docker-compose*.yml`의 `${변수}`를 채운다 |
| 기동 | 각 모듈 폴더의 README와 `Dockerfile` · `docker-compose*.yml`을 따른다 |

## 평가 자료

| 경로 | 내용 |
|---|---|
| `index/graph-index/scripts/graph_rag_poc/data/chunks/` | 합성 문서 집합(가상 기업 「Autonova」): 정답 청크 40개 + 방해 청크 960개 = 1,000청크, 200 · 500청크 축소판 |
| `index/graph-index/scripts/graph_rag_poc/data/qa/` | 합성 골든 Q&A 52문: 기본 20, 관계 종합(fan-out) 8, 환각 함정 12, 관계 유형 12 |
| `index/graph-index/scripts/graph_rag_poc/experiments/` | 실험 설정 61개, 실험별 측정 원장 `LEDGER.md`, 요약 `../CAMPAIGN_SUMMARY.md` |
| `index/graph-index/scripts/graph_eval/` | LLM 기반 골든셋 자동 생성 코드 |
| `eval/results/` | 사내 문서 기반 골든셋 81문 측정 결과(수치) |

※ 합성 데이터의 인물 · 기관 · 수치는 모두 가상이다. 사내 문서와 그 문서로 만든 골든셋 원문은 공개하지 않는다.

## 측정 결과 요약

사내 문서 기반 골든셋 81문, recall@10(정답 청크 회수율), 2026-06-25 측정. 상세는 `eval/results/README.md`.

| 질의 유형 | 문항 | 벡터 | 그래프 | Hybrid(벡터 + 그래프) |
|---|---|---|---|---|
| 개체 종합형 | 46 | 0.284 | 0.488 | 0.581 |
| 단일 사실형 | 35 | 0.629 | 0.171 | 0.686 |
| **전체** | **81** | **0.433** | **0.351** | **0.627** |

## 라이선스

Apache License 2.0. 전문은 `LICENSE`.
