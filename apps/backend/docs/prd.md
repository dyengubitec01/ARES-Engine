---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
inputDocuments:
  - docs/analysis/product-brief-backend-2025-12-09.md
  - docs/analysis/brainstorming-session-2025-12-09.md
documentCounts:
  briefs: 1
  research: 0
  brainstorming: 1
  projectDocs: 0
workflowType: 'prd'
lastStep: 11
status: complete
project_name: 'backend'
user_name: 'ARES team'
date: '2025-12-09'
---

# Product Requirements Document - backend

**Author:** ARES team
**Date:** 2025-12-09

---

## Executive Summary

**backend**는 사내 직원을 위한 통합 AI 게이트웨이 백엔드입니다.

여러 AI 서비스(Chatbot Agent, RAG 임베딩, MinIO, PostgreSQL, Kafka)를 하나로 연결하여, Azure AD로 인증된 직원만 사용할 수 있는 맞춤형 사내 AI 솔루션을 제공합니다.

### 핵심 문제

- 사내 문서 검색에 불필요한 시간 소모
- 외부 AI 서비스 사용 시 보안 위험
- 사내 전용 AI 솔루션 부재

### What Makes This Special

1. **사내 전용**: Azure AD 인증으로 보안 확보
2. **문서 기반 AI**: RAG로 사내 문서 기반 답변 제공
3. **통합 게이트웨이**: 여러 AI 서비스를 하나로 연결
4. **실시간 스트리밍**: SSE로 빠른 응답 경험

## Project Classification

| 항목 | 값 |
|------|-----|
| **Technical Type** | api_backend |
| **Domain** | general (사내 도구) |
| **Complexity** | low |
| **Project Context** | Greenfield - new project |

---

## Success Criteria

### User Success

| 지표 | 설명 | 측정 방법 |
|------|------|----------|
| 답변 정확도 | AI가 관련 문서와 함께 정확한 답변 제공 | 피드백 긍정률 |
| 피드백 긍정률 | 사용자 좋아요 비율 | 좋아요 수 / 전체 피드백 |

**피드백 시스템:**
- 좋아요/싫어요: 각 AI 답변에 피드백 가능
- 데이터 활용: 좋아요 받은 답변은 다음 임베딩 학습에 활용
- DB 구조: 답변 테이블에 `like_yn` 컬럼으로 저장

### Business Success

| 목표 | 설명 |
|------|------|
| 사용률 증가 | 전체 직원 중 활성 사용자 비율 증가 |
| DAU | Daily Active Users 추적 |
| 질문 수 | 일일/주간 총 질문 수 |
| 피드백 참여율 | 답변 중 피드백을 남긴 비율 |

### Technical Success

- SSE 연결 안정성: 헬스체크로 연결 상태 지속 확인
- API 응답 시간: 합리적인 응답 속도 유지
- Azure AD 인증 성공률: 100% 인증 처리

### Measurable Outcomes (KPIs)

| KPI | 목표 |
|-----|------|
| 피드백 긍정률 | > 70% |
| 피드백 참여율 | > 30% |
| 주간 활성 사용자 | 전 직원의 > 50% |

---

## Product Scope

### MVP - 1차 (Auth + Chat)

| 기능 | 설명 |
|------|------|
| Azure AD 로그인 | 사내 직원 인증 |
| AI 질문 | Chatbot Agent에 질문 전송 |
| SSE 스트리밍 답변 | 실시간 AI 응답 |
| 피드백 | 답변에 좋아요/싫어요 |
| 헬스체크 | SSE 연결 상태 모니터링 |

### Growth Features - 2차 (File + Document + RAG)

- MinIO 파일 저장소 연동
- 문서 CRUD 기능
- RAG 임베딩 요청 및 문서 검색
- "질문하면 관련 문서와 함께 AI가 답변"

### Vision - 3차 (Event)

- Kafka 이벤트 로깅
- 사용 패턴 분석
- 시스템 모니터링

---

## User Journeys

### Journey 1: 김민수 - 업무 질문에 빠른 답변을 찾다

김민수는 마케팅팀 신입사원이다. 새로운 프로젝트를 맡았는데, 회사 브랜드 가이드라인에 대해 잘 모른다. 예전 같으면 선배에게 물어보거나 공유폴더를 뒤져야 했다.

오늘 아침, 김민수는 Azure AD로 로그인하여 사내 AI 시스템에 접속한다. "브랜드 로고 사용 규정이 어떻게 되나요?"라고 질문을 입력한다. SSE 스트리밍으로 실시간으로 답변이 나타나기 시작한다. AI는 브랜드 가이드라인 문서를 참조하여 로고 사용 규정을 상세히 설명해준다.

답변이 정확해서 김민수는 좋아요 버튼을 누른다. 이제 선배를 방해하지 않고도 필요한 정보를 빠르게 찾을 수 있다. 김민수는 업무 시간의 30%를 문서 검색에서 실제 업무로 전환할 수 있게 되었다.

**이 여정에서 드러나는 요구사항:**
- Azure AD 로그인/인증
- 질문 입력 및 전송
- SSE 스트리밍 답변 표시
- 피드백 (좋아요/싫어요) 기능

---

### Journey 2: 김민수 - 연결 오류 상황

김민수가 질문을 입력했는데 답변이 오지 않는다. 시스템은 SSE 연결 상태를 헬스체크하고 있다가 연결 실패를 감지한다. 화면에 "AI 서버 연결 중... 잠시만 기다려주세요"라는 메시지가 표시된다.

헬스체크가 계속 시도되고, 연결이 복구되면 자동으로 질문이 다시 전송된다. 김민수는 별도의 조치 없이 답변을 받을 수 있다.

**이 여정에서 드러나는 요구사항:**
- SSE 헬스체크 및 연결 상태 모니터링
- 연결 실패 시 사용자 알림
- 자동 재연결 및 재시도 로직

---

### Journey 3: 박지영 관리자 - 권한 관리

박지영은 IT팀 관리자다. 새로 입사한 데이터팀 직원에게 임베딩 요청 권한을 부여해야 한다.

박지영은 관리자 계정으로 로그인하여 권한 관리 화면에 접속한다. 사용자 목록에서 새 직원을 찾아 "임베딩 요청" 권한을 체크하고 저장한다. 이제 해당 직원은 새로운 문서를 임베딩 요청할 수 있다.

나중에 조직 개편으로 새로운 권한 유형이 필요해지면, 박지영은 새로운 권한을 생성하여 필요한 사용자에게 부여할 수 있다.

**이 여정에서 드러나는 요구사항:**
- 관리자 권한 구분 (DB 컬럼)
- 사용자 목록 조회
- 권한 부여/회수 기능
- 확장 가능한 권한 시스템

---

### Journey Requirements Summary

| 기능 영역 | 요구사항 |
|----------|---------|
| **인증** | Azure AD 로그인, 관리자 권한 구분 |
| **채팅** | 질문 입력, SSE 스트리밍 답변 |
| **연결 관리** | 헬스체크, 연결 실패 알림, 자동 재연결 |
| **피드백** | 좋아요/싫어요, DB 저장 |
| **권한 관리** | 사용자 조회, 권한 부여/회수, 확장 가능한 권한 |

---

## API Backend Specific Requirements

### Project-Type Overview

NestJS 기반 API 백엔드로, 여러 외부 서비스를 연결하는 게이트웨이 역할을 수행합니다.

### Endpoint Specification

| 모듈 | 엔드포인트 | 메서드 | 설명 |
|------|-----------|--------|------|
| **Auth** | /auth/login | POST | Azure AD OAuth 로그인 |
| **Auth** | /auth/refresh | POST | 토큰 갱신 |
| **Chat** | /chat | POST (SSE) | AI 질문 및 스트리밍 답변 |
| **Chat** | /chat/feedback | POST | 답변 피드백 (좋아요/싫어요) |
| **Chat** | /chat/health | GET | SSE 연결 헬스체크 |
| **Admin** | /admin/users | GET | 사용자 목록 조회 |
| **Admin** | /admin/permissions | PUT | 권한 부여/회수 |

### Authentication Model

| 항목 | 값 |
|------|-----|
| **Provider** | Azure AD (OAuth 2.0) |
| **Token Type** | JWT (Access + Refresh) |
| **Token Management** | 백엔드에서 Refresh Token 갱신 |
| **Authorization** | DB 컬럼 기반 관리자/일반 사용자 구분 |

### Data Schemas

**Request/Response Format:** JSON
**Streaming Format:** SSE (Server-Sent Events)

### Error Codes

| 코드 | 설명 |
|------|------|
| 401 | 인증 실패 |
| 403 | 권한 없음 |
| 503 | AI 서버 연결 실패 |

### Technical Architecture Considerations

- **Framework:** NestJS
- **Database:** PostgreSQL + TypeORM
- **External Services:** Chatbot Agent (SSE), RAG Server (REST), MinIO (S3), Kafka
- **Connection Management:** SSE 헬스체크 기반 연결 상태 모니터링

---

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP
- 핵심 문제(사내 문서 검색 시간 소모)를 최소 기능으로 해결
- 빠른 검증 후 단계적 확장

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- Journey 1: 김민수 - 업무 질문에 빠른 답변
- Journey 2: 김민수 - 연결 오류 복구

**Must-Have Capabilities:**
- Azure AD 로그인/인증
- AI 질문 전송 및 SSE 스트리밍 답변
- 피드백 (좋아요/싫어요)
- 헬스체크 및 연결 복구

### Post-MVP Features

**Phase 2 (Growth):**
- MinIO 파일 저장소 연동
- 문서 CRUD
- RAG 임베딩 및 문서 검색
- Journey 3: 박지영 관리자 - 권한 관리 완전 지원

**Phase 3 (Expansion):**
- Kafka 이벤트 로깅
- 사용 패턴 분석
- 시스템 모니터링

### Risk Mitigation Strategy

| 리스크 유형 | 리스크 | 대응 |
|-------------|--------|------|
| Technical | SSE 연결 불안정 | 헬스체크 + 자동 재연결 |
| Technical | 외부 서비스 장애 | 503 에러 코드 + 사용자 알림 |
| Resource | 개발 인력 부족 | MVP 범위 최소화로 대응 |

---

## Functional Requirements

### 인증 (Authentication)

- FR1: 사용자는 Azure AD 계정으로 로그인할 수 있다
- FR2: 시스템은 Access Token 만료 시 Refresh Token으로 자동 갱신할 수 있다
- FR3: 시스템은 사용자를 일반/관리자로 구분할 수 있다

### 채팅 (Chat)

- FR4: 사용자는 AI에게 텍스트 질문을 전송할 수 있다
- FR5: 사용자는 AI 답변을 SSE 스트리밍으로 실시간 수신할 수 있다
- FR6: 사용자는 AI 답변에 좋아요/싫어요 피드백을 남길 수 있다
- FR7: 시스템은 피드백 데이터를 저장하고 조회할 수 있다

### 연결 관리 (Connection Management)

- FR8: 시스템은 Chatbot Agent 연결 상태를 헬스체크할 수 있다
- FR9: 시스템은 연결 실패 시 사용자에게 알림을 표시할 수 있다
- FR10: 시스템은 연결 복구 시 자동으로 재시도할 수 있다

### 권한 관리 (Permission Management) - Phase 2

- FR11: 관리자는 전체 사용자 목록을 조회할 수 있다
- FR12: 관리자는 사용자에게 권한을 부여/회수할 수 있다
- FR13: 시스템은 확장 가능한 권한 체계를 지원할 수 있다

### 문서 관리 (Document Management) - Phase 2

- FR14: 사용자는 MinIO에 파일을 업로드할 수 있다
- FR15: 사용자는 문서를 생성/조회/수정/삭제할 수 있다
- FR16: 사용자는 문서 임베딩을 요청할 수 있다
- FR17: 시스템은 RAG를 통해 관련 문서와 함께 답변을 제공할 수 있다

### 이벤트 로깅 (Event Logging) - Phase 3

- FR18: 시스템은 사용자 활동을 Kafka로 로깅할 수 있다
- FR19: 시스템은 사용 패턴 데이터를 분석용으로 제공할 수 있다

---

## Non-Functional Requirements

### Performance

| 요구사항 | 기준 |
|----------|------|
| API 응답 시간 | 일반 API < 500ms |
| SSE 첫 응답 | < 2초 (AI 서버 응답 제외) |
| 헬스체크 주기 | 10초 |
| 동시 접속 | 사내 직원 수 기준 (100명 이하) |

### Security

| 요구사항 | 기준 |
|----------|------|
| 인증 | Azure AD OAuth 2.0 필수 |
| 토큰 저장 | Refresh Token 서버 측 관리 |
| 데이터 전송 | HTTPS 필수 |
| 권한 검증 | 모든 API 요청에 토큰 검증 |

### Integration

| 요구사항 | 기준 |
|----------|------|
| Chatbot Agent 연결 | 연결 실패 시 503 반환 + 재시도 |
| RAG Server 연결 | 타임아웃 30초 |
| MinIO 연결 | 파일 업로드 최대 100MB |
| Kafka 연결 | 비동기 전송, 실패 시 로컬 버퍼링 |
