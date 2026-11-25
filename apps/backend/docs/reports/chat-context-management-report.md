# 채팅 컨텍스트 관리 시스템 보고서

**작성일:** 2026-01-16
**작성자:** SM Agent (Bob)
**프로젝트:** backend - 사내 AI 게이트웨이

---

## 1. 개요

본 보고서는 **채팅 컨텍스트 관리 시스템**의 구현 내용을 설명합니다. 이 시스템은 Redis 캐시와 Tools API를 활용하여 대화 요약본을 관리하고, AI Chatbot에게 적절한 컨텍스트를 전달하여 토큰 사용량을 최적화하면서 대화 흐름을 유지합니다.

**핵심 기능:**
- Redis 캐시를 통한 대화 요약본 저장/조회
- Tools API를 통한 대화 히스토리 요약 생성
- 세션 삭제 시 캐시 자동 정리

---

## 2. 도입 배경

### 2.1 기존 방식의 문제점

전체 대화 히스토리를 매번 Chatbot에 전달하는 방식:

```
사용자 질문 → 전체 히스토리 조회 → 히스토리 + 질문 → Chatbot
```

**문제점:**
1. **토큰 비용 증가**: 대화가 길어질수록 토큰 사용량 급증
2. **응답 지연**: 긴 컨텍스트 처리로 인한 응답 시간 증가
3. **컨텍스트 제한**: LLM의 컨텍스트 윈도우 초과 가능성

### 2.2 요약본 캐시 방식의 장점

```
사용자 질문 → Redis 캐시 확인 → 요약본 + 질문 → Chatbot
                   │
                   └── 캐시 미스 시 Tools API 호출
```

**이점:**
1. ✅ **토큰 절약**: 전체 히스토리 대신 요약본만 전달
2. ✅ **응답 속도 향상**: Redis 캐시 hit 시 즉시 응답
3. ✅ **일관성 유지**: 요약본으로 대화 맥락 보존

---

## 3. 전체 아키텍처

### 3.1 시스템 구성

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│              │      │              │      │              │
│   Frontend   │◄────►│   Backend    │◄────►│  AI Chatbot  │
│   (React)    │      │  (NestJS)    │      │  (Python)    │
│              │      │              │      │              │
└──────────────┘      └──────┬───────┘      └──────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │    Redis     │  │  PostgreSQL  │  │  Tools API   │
    │ (요약본 캐시) │  │   (히스토리) │  │ (요약 생성)  │
    └──────────────┘  └──────────────┘  └──────────────┘
```

### 3.2 컴포넌트 역할

| 컴포넌트 | 역할 |
|----------|------|
| **RedisService** | 세션별 요약본 캐시 관리 |
| **ToolsService** | 히스토리 요약 API 호출 |
| **ChatService** | 컨텍스트 조회 및 Chatbot 연동 |
| **Redis** | 요약본 캐시 저장소 |
| **Tools API** | 대화 히스토리 요약 생성 |

### 3.3 Redis 키 패턴

```
키: session:{sessionId}:summary
값: 대화 요약본 텍스트
TTL: 없음 (세션 삭제 시 함께 삭제)
```

---

## 4. 컨텍스트 조회 플로우

### 4.1 전체 플로우 다이어그램

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    컨텍스트 조회 플로우 (getSessionContext)                   │
└────────────────────────────────────────────────────────────────────────────┘

사용자 질문
    │
    ▼
┌─────────────────────────────────────────┐
│  Step 1. Redis 캐시 확인                 │
│  key: session:{sessionId}:summary       │
└─────────────────────────────────────────┘
    │
    ├── Cache Hit ────────────────────────► 요약본 + 질문 → Chatbot
    │   (source: 'redis')
    │
    └── Cache Miss
        │
        ▼
┌─────────────────────────────────────────┐
│  Step 2. RDB 히스토리 확인               │
│  SELECT * FROM chat_interactions        │
│  WHERE session_id = :sessionId          │
└─────────────────────────────────────────┘
        │
        ├── 히스토리 있음 ─────────────────► 슬라이딩 윈도우 분리 (Story 2.13)
        │                                      │
        │                                      ├─── 이전 히스토리 → Tools API 호출 (동기)
        │                                      │         │
        │                                      │         ▼
        │                                      │     요약본 반환 (Tools가 Redis 저장)
        │                                      │
        │                                      └─── 최근 10쌍 → 원본 유지 (recentHistory)
        │                                                │
        │                                                ▼
        │                                  요약본 + 최근 히스토리 + 질문 → Chatbot
        │                                  (source: 'tools')
        │
        └── 히스토리 없음 (첫 질문) ────────► 질문만 → Chatbot
                                            (source: 'none')
```

### 4.2 시퀀스 다이어그램

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    채팅 컨텍스트 조회 시퀀스                                   │
└────────────────────────────────────────────────────────────────────────────┘

[Frontend]          [ChatService]        [RedisService]   [ToolsService]    [Chatbot]
    │                    │                     │                │               │
    │ POST /chat/sessions/:id/interactions     │                │               │
    │ ──────────────────►│                     │                │               │
    │                    │                     │                │               │
    │                    │ getSessionSummary() │                │               │
    │                    │ ───────────────────►│                │               │
    │                    │                     │                │               │
    │                    │ ◄─── null (miss)    │                │               │
    │                    │                     │                │               │
    │                    │   (RDB 히스토리 조회)│                │               │
    │                    │                     │                │               │
    │                    │ summarizeHistory()  │                │               │
    │                    │ ────────────────────────────────────►│               │
    │                    │                     │                │               │
    │                    │ ◄─── 요약본 반환    │  (Redis 저장)  │               │
    │                    │                     │                │               │
    │                    │ 요약본 + 질문       │                │               │
    │                    │ ──────────────────────────────────────────────────►  │
    │                    │                     │                │               │
    │ SSE 응답 (AI 답변) │                     │                │               │
    │ ◄──────────────────│                     │                │               │
```

### 4.3 단계별 상세 설명

#### **Case 1: Redis 캐시 Hit (AC1)**

가장 빠른 경로로, 이전에 Tools가 생성한 요약본이 Redis에 존재하는 경우입니다.

```typescript
// ChatService.getSessionContext()
const cachedSummary = await this.redisService.getSessionSummary(sessionId);
if (cachedSummary) {
  return {
    summary: cachedSummary,
    isFirstQuestion: false,
    source: 'redis'
  };
}
```

---

#### **Case 2: 캐시 미스 + 히스토리 있음 (AC2)**

Redis에 캐시가 없지만 DB에 대화 히스토리가 있는 경우, Tools API를 호출합니다.

**Story 2.13 Enhancement (2026-01-22):** 슬라이딩 윈도우 일관성 유지를 위해 최근 10쌍은 원본으로 유지하고, 이전 히스토리만 요약합니다.

```typescript
// Story 2.13 Fix: Maintain sliding window consistency when Redis is lost
// Keep recent 10 pairs as original, only summarize older ones
const allHistoryFormatted = history.map((h) => ({
  type: h.type as 'Q' | 'A',
  content: h.content,
  chatTurn: h.chatTurn,
}));

// Group by chatTurn to count pairs
const pairCount = Math.max(...history.map((h) => h.chatTurn));
const recentPairThreshold = Math.max(1, pairCount - COMPRESSION_BATCH_SIZE + 1);

// Split history: older pairs to summarize, recent pairs to keep as original
const olderHistory = allHistoryFormatted.filter((h) => h.chatTurn < recentPairThreshold);
const recentHistory = allHistoryFormatted.filter((h) => h.chatTurn >= recentPairThreshold);

// Only call Tools API if there are older pairs to summarize
let summary: string | null = null;
if (olderHistory.length > 0) {
  summary = await this.toolsService.summarizeHistory(sessionId, olderHistory);
}

return {
  summary,
  isFirstQuestion: false,
  source: 'tools',
  recentHistory: recentHistory.length > 0 ? recentHistory : undefined,
};
```

**중요:**
- Tools API가 요약본을 생성하면서 **Redis에 직접 저장**합니다
- Backend는 요약본만 받아서 Chatbot에 전달합니다
- **Story 2.13 Fix:** 최근 10쌍(recentHistory)은 원본으로 유지하여 정상 케이스와 동일한 컨텍스트 구조 보장

---

#### **Case 3: 첫 질문 (AC3)**

캐시도 없고 히스토리도 없는 첫 질문의 경우입니다.

```typescript
if (history.length === 0) {
  return {
    summary: null,
    isFirstQuestion: true,
    source: 'none'
  };
}
```

---

## 5. 세션 삭제 시 캐시 정리 (AC4)

채팅방 삭제 시 Redis 캐시도 함께 삭제하여 데이터 정합성을 유지합니다.

```
┌────────────────────────────────────────────────────────────────┐
│                    세션 삭제 플로우                                │
└────────────────────────────────────────────────────────────────┘

[Frontend]              [ChatService]         [Redis]         [PostgreSQL]
    │                        │                   │                  │
    │ DELETE /chat/sessions/:id                  │                  │
    │ ──────────────────────►│                   │                  │
    │                        │                   │                  │
    │                        │ DEL session:*:summary                │
    │                        │ ─────────────────►│                  │
    │                        │                   │                  │
    │                        │ DELETE chat_sessions                 │
    │                        │ ──────────────────────────────────► │
    │                        │                   │                  │
    │ 200 OK                 │                   │                  │
    │ ◄──────────────────────│                   │                  │
```

```typescript
// ChatService.deleteSession()
async deleteSession(sessionId: string, userId: string): Promise<void> {
  // 1. Redis 캐시 삭제
  await this.redisService.deleteSessionSummary(sessionId);

  // 2. DB 레코드 삭제 (CASCADE)
  await this.sessionRepository.delete({ id: sessionId, userId });
}
```

---

## 6. Tools API 인터페이스

### 6.1 POST /summarize

히스토리를 받아 요약본을 생성합니다.

**요청:**
```typescript
interface SummarizeRequest {
  sessionId: string;
  history: Array<{
    type: 'Q' | 'A';     // Q: 사용자 질문, A: AI 답변
    content: string;
    chatTurn: number;
  }>;
}
```

**응답:**
```typescript
interface SummarizeResponse {
  summary: string;       // 생성된 요약본
}
```

**예시:**
```json
// Request
{
  "sessionId": "session-123",
  "history": [
    { "type": "Q", "content": "RAG가 뭐야?", "chatTurn": 1 },
    { "type": "A", "content": "RAG는 Retrieval-Augmented Generation의 약자로...", "chatTurn": 1 },
    { "type": "Q", "content": "어디에 쓰여?", "chatTurn": 2 },
    { "type": "A", "content": "RAG는 문서 검색 기반 QA 시스템에서 주로...", "chatTurn": 2 }
  ]
}

// Response
{
  "summary": "사용자가 RAG(Retrieval-Augmented Generation)의 개념과 활용처에 대해 질문함. RAG는 문서 검색과 텍스트 생성을 결합한 기술로, 주로 QA 시스템에서 활용됨."
}
```

### 6.2 GET /health

Tools API 상태 확인용 헬스체크 엔드포인트입니다.

```typescript
// ToolsService.healthCheck()
async healthCheck(): Promise<boolean> {
  const response = await fetch(`${this.toolsUrl}/health`);
  return response.ok;
}
```

---

## 7. 환경 변수 설정

### 7.1 필수 환경 변수

```env
# Redis 설정 (비활성화 시 주석 처리)
# REDIS_HOST=redis.example.com
# REDIS_PORT=6379

# Tools API 설정 (비활성화 시 주석 처리)
# TOOLS_API_URL=http://tools.example.com
```

### 7.2 환경변수 기반 서비스 활성화

```typescript
// external.config.ts
redis: {
  host: process.env.REDIS_HOST || '',  // 빈 값이면 비활성화
  port: parseInt(process.env.REDIS_PORT || '6379', 10),
},
tools: {
  url: process.env.TOOLS_API_URL || '',  // 빈 값이면 비활성화
},
```

**중요:** 환경 변수가 설정되지 않으면 (빈 값) 해당 서비스는 자동으로 비활성화됩니다.

### 7.3 Redis 비활성화 모드

Redis가 설정되지 않은 경우, 연결 시도 없이 graceful하게 동작합니다:

```typescript
// RedisService
constructor(private configService: ConfigService) {
  const host = this.configService.get<string>('external.redis.host');

  if (!host) {
    this.enabled = false;
    this.logger.warn('Redis not configured - running in disabled mode');
    return;
  }

  this.enabled = true;
  this.client = new Redis({
    host,
    port: this.configService.get<number>('external.redis.port'),
  });
}

async getSessionSummary(sessionId: string): Promise<string | null> {
  if (!this.enabled) return null;  // 비활성화 시 캐시 미스로 처리
  // ...
}
```

---

## 8. 모듈 구조

### 8.1 RedisModule

```typescript
// src/external/redis/redis.module.ts
@Global()
@Module({
  providers: [RedisService],
  exports: [RedisService],
})
export class RedisModule {}
```

**특징:**
- `@Global()` 데코레이터로 전역 모듈 설정
- AppModule에서 한 번만 import하면 어디서든 사용 가능

### 8.2 ToolsModule

```typescript
// src/external/tools/tools.module.ts
@Module({
  providers: [ToolsService],
  exports: [ToolsService],
})
export class ToolsModule {}
```

**의존성:**
- ChatModule에서 import하여 사용

---

## 9. 테스트

### 9.1 테스트 케이스

| 테스트 | 설명 | AC |
|--------|------|-----|
| Redis 캐시 hit 테스트 | 캐시된 요약본 반환 확인 | AC1 |
| 캐시 미스 + Tools 호출 테스트 | Tools API 호출 및 요약본 반환 확인 | AC2 |
| 첫 질문 (skip Tools) 테스트 | 히스토리 없을 때 Tools 호출 안함 확인 | AC3 |
| 세션 삭제 시 캐시 삭제 테스트 | Redis 키 삭제 확인 | AC4 |

### 9.2 테스트 결과

```
✓ RedisService - getSessionSummary returns cached summary
✓ RedisService - getSessionSummary returns null when disabled
✓ ToolsService - summarizeHistory returns summary from API
✓ ToolsService - summarizeHistory returns null on error
✓ ChatService - getSessionContext returns redis cache when hit
✓ ChatService - getSessionContext calls tools when cache miss
✓ ChatService - getSessionContext skips tools for first question
✓ ChatService - deleteSession removes redis cache

28 tests passed
```

---

## 10. 에러 처리

### 10.1 Redis 연결 실패

Redis 연결 실패 시에도 서비스는 정상 동작합니다 (graceful degradation).

```typescript
// RedisService
async getSessionSummary(sessionId: string): Promise<string | null> {
  if (!this.enabled) return null;

  try {
    return await this.client.get(key);
  } catch (error) {
    this.logger.error('Redis get error', error);
    return null;  // 캐시 미스로 처리
  }
}
```

### 10.2 Tools API 연결 실패

Tools API 오류 시에도 요약 없이 질문만 전달됩니다.

```typescript
// ToolsService
async summarizeHistory(sessionId: string, history: HistoryItem[]): Promise<string | null> {
  try {
    const response = await fetch(`${this.toolsUrl}/summarize`, { ... });
    if (!response.ok) return null;
    return (await response.json()).summary;
  } catch (error) {
    this.logger.error('Tools API error', error);
    return null;  // 요약 없이 진행
  }
}
```

---

## 11. 관련 파일

### 11.1 신규 생성 파일

| 파일 | 역할 |
|------|------|
| [redis.module.ts](../../src/external/redis/redis.module.ts) | Redis 모듈 정의 |
| [redis.service.ts](../../src/external/redis/redis.service.ts) | Redis 서비스 (캐시 관리) |
| [redis.service.spec.ts](../../src/external/redis/redis.service.spec.ts) | Redis 서비스 테스트 |
| [tools.module.ts](../../src/external/tools/tools.module.ts) | Tools API 모듈 정의 |
| [tools.service.ts](../../src/external/tools/tools.service.ts) | Tools API 클라이언트 |
| [tools.service.spec.ts](../../src/external/tools/tools.service.spec.ts) | Tools 서비스 테스트 |

### 11.2 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| [external.config.ts](../../src/config/external.config.ts) | redis, tools 설정 추가 |
| [app.module.ts](../../src/app.module.ts) | RedisModule import 추가 |
| [chat.module.ts](../../src/chat/chat.module.ts) | ToolsModule import 추가 |
| [chat.service.ts](../../src/chat/chat.service.ts) | getSessionContext(), deleteSession() 수정 |
| [chat.service.spec.ts](../../src/chat/chat.service.spec.ts) | 테스트 업데이트 |
| [.env](../../.env) | Redis, Tools 환경변수 추가 (주석 처리) |

---

## 12. 키 설계 결정사항

| 결정 | 이유 |
|------|------|
| Tools가 Redis 저장 담당 | Backend는 요약본만 사용, 저장 책임 분리 |
| 동기 호출 방식 | 요약본 없이 Chatbot 호출 시 맥락 손실 |
| 환경변수 기반 활성화 | 서비스 미연결 시 에러 없이 동작 |
| Global Redis 모듈 | 여러 모듈에서 공용 사용 가능 |

---

## 13. 향후 개선사항

1. **TTL 설정**: 오래된 세션의 캐시 자동 만료
2. **캐시 갱신 정책**: Tools가 주기적으로 요약본 갱신
3. **모니터링**: Redis 캐시 hit/miss 비율 추적

---

## 14. 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-01-16 | 1.0 | 초기 작성 - Story 2.10 구현 |

---

**문서 끝**
