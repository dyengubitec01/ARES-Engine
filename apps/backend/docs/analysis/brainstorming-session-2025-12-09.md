---
stepsCompleted: [1, 2]
inputDocuments: []
session_topic: 'NestJS API 개발 접근 방식'
session_goals: 'API 구조 설계, 기능별 구현 순서, 테스트 전략'
selected_approach: 'AI-Recommended'
techniques_used: ['Six Thinking Hats', 'First Principles Thinking', 'Decision Tree Mapping']
ideas_generated: []
context_file: 'docs/bmm-workflow-status.yaml'
---

# Brainstorming Session Results

**Facilitator:** ARES team
**Date:** 2025-12-09

## Session Overview

**Topic:** NestJS 백엔드 API 개발 전략
**Goals:**
- API 구조 설계
- 기능별 구현 순서
- 테스트 전략 (TDD/테스트 커버리지)

**Scope:** 6개 기능
1. 사용자 인증 관리
2. 문서 관리
3. 임베딩 요청 (AI/Vector)
4. 이벤트 상태관리
5. 채팅방 관리
6. AI 채팅 관리

---

## Technique 1: Six Thinking Hats

### White Hat (사실)
| 항목 | 내용 |
|------|------|
| **Framework** | NestJS |
| **DB** | PostgreSQL + TypeORM (서버 있음, 연결만) |
| **우선순위** | 1) 사용자 권한 관리 → 2) AI 질문 API |
| **LLM** | 외부 서버 API 호출, SSE 스트리밍 응답 |
| **임베딩** | 외부 서버, API 호출 모양만 갖추기 |
| **테스트** | Jest |
| **배포** | 미정 |

### Yellow Hat (장점)
- 외부 LLM 분리: 백엔드는 API 호출만, LLM 로직 부담 없음
- SSE 스트리밍: 실시간 UX
- TypeORM: 타입 안전성, 마이그레이션 관리 용이
- NestJS 모듈화: 기능별 모듈 분리로 유지보수 쉬움

### Black Hat (위험)
- **SSE 연결 관리 (최우선)**: 헬스체크로 연결 상태 지속 확인
- 연결 끊김 감지: Heartbeat/Ping 메커니즘
- 자동 재연결 로직 필요

### Green Hat (아이디어)
- ✅ 채택: 헬스체크 기반 연결 관리 (연결 안됨 → 알림 → 체크 → API 호출)
- ⏸️ 대기: Circuit Breaker, 메시지 큐 백업, 연결 풀링

### Blue Hat (정리)
1. 인증 먼저 → AI API 순서로 개발
2. SSE 헬스체크 필수 구현
3. 연결 실패 시 사용자에게 명확히 알림
4. 테스트: Jest로 Unit + E2E

---

## Technique 2: First Principles Thinking

### 핵심 목적
> "이 백엔드는 **다른 모델들을 연결**하기 위해 존재한다" (AI 모델 게이트웨이/허브)

### 연결 대상
| 서버 | 역할 | 연결 방식 |
|------|------|----------|
| **Chatbot Agent** | AI 대화 | SSE 스트리밍 |
| **RAG 임베딩** | 문서 벡터화/검색 | REST API |
| **Kafka** | 이벤트 로깅 | Kafka Client |
| **PostgreSQL** | 데이터 저장 | TypeORM |
| **MinIO** | 파일 저장 | S3 API |

### 모듈 구조
```
┌──────────┬──────────┬──────────┬──────────┬─────────┐
│   Auth   │   Chat   │   RAG    │  Event   │  File   │
│  Module  │  Module  │  Module  │  Module  │ Module  │
├──────────┼──────────┼──────────┼──────────┼─────────┤
│ Azure AD │ Chatbot  │ 임베딩   │  Kafka   │  MinIO  │
│  OAuth   │   SSE    │  API     │ 이벤트   │   S3    │
│ Refresh  │ 헬스체크  │          │  로깅    │  API    │
└──────────┴──────────┴──────────┴──────────┴─────────┘
```

### 미정 사항
- Kafka 채팅 메시지 보존 용도: 추후 결정

---

## Technique 3: Decision Tree Mapping

### 최종 구현 순서 (의존성 기반)

| 순서 | 모듈 | 설명 | 테스트 |
|------|------|------|--------|
| 1️⃣ | **Auth** | Azure AD OAuth, Refresh Token 갱신 (백엔드) | Unit + E2E |
| 2️⃣ | **File** | MinIO 연결, 파일 업로드/다운로드 | Unit + Integration |
| 3️⃣ | **Document** | 문서 CRUD, 파일 연동 | Unit + E2E |
| 4️⃣ | **RAG** | 임베딩 서버 API 호출 | Unit + Integration |
| 5️⃣ | **Chat** | SSE, 헬스체크, 채팅방 | Unit + E2E |
| 6️⃣ | **Event** | Kafka 이벤트 로깅 | Integration |

### Auth 모듈 상세
| 항목 | 내용 |
|------|------|
| **인증 방식** | Azure AD (OAuth 2.0) |
| **토큰** | Azure Refresh Token 사용 |
| **토큰 갱신** | 백엔드에서 처리 |
| **구현** | NestJS + Passport Azure AD |

---

## Summary & Next Steps

### 핵심 결정 사항
1. **아키텍처**: NestJS 게이트웨이 (5개 외부 서버 연결)
2. **인증**: Azure AD OAuth + 백엔드 토큰 갱신
3. **구현 순서**: Auth → File → Document → RAG → Chat → Event
4. **테스트**: Jest (Unit + E2E + Integration)
5. **핵심 위험**: SSE 연결 관리 → 헬스체크 필수

### 다음 단계
- [ ] Product Brief 작성
- [ ] PRD 작성
- [ ] Architecture 문서 작성
