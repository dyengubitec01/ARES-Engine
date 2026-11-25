# Story 3.3: 프롬프트 품질 개선 + RAG 필수 경유

## Enhancement Story

**Parent:** Epic 3 (답변 품질 + RAG 검색 안정화)
**Type:** Enhancement
**Branch:** feat/prompt-quality-rag-routing

## 배경

### 1. Synthesizer 프롬프트 한계
현재 Synthesizer 프롬프트가 "검색된 문서 기반으로 답변"이라는 일반적 지시만 포함.
실제 운영에서 다음 문제 발생:
- 답변이 지나치게 짧거나, 반대로 불필요하게 장황한 경우
- 문서 내용을 그대로 복사하여 가독성이 떨어지는 경우
- 사용자 질문의 맥락을 충분히 반영하지 못하는 경우

### 2. RAG 필수 경유 지시
모든 질문을 RAG를 경유하도록 지시사항이 내려옴.
기존 `SKIP_RAG`, `SKIP_TOOL`과 동일한 패턴으로 `SKIP_DIRECT` 환경변수를 추가하여
direct 경로를 on/off 제어한다. `SKIP_DIRECT=true` 시 모든 질문이 RAG를 거친다.

### 3. Rewriter 재구성 품질
대명사 해소 시 원문의 의도를 벗어나거나, 불필요한 키워드를 추가하는 경우 간헐적 발생.

## 수정 항목

### A. Synthesizer 프롬프트 상세화

**수정 방향:**
- RAG 답변 프롬프트에 답변 깊이/구체성 가이드 강화
- 문서 내용 요약 vs 인용 기준 명확화
- 질문 유형별 답변 전략 추가 (절차 질문 → 단계별, 비교 질문 → 표 형식 등)

**영향 파일:**
- `app/workflows/main_agent/prompts/synthesizer.py`

### B. SKIP_DIRECT 환경변수 추가

기존 `SKIP_RAG`, `SKIP_TOOL`과 동일한 패턴으로 `SKIP_DIRECT` 추가.

- `SKIP_DIRECT=true` → direct 경로 비활성, 모든 질문 RAG 경유
- `SKIP_DIRECT=false` → 기존처럼 일반 상식/인사는 direct 허용

**SKIP 매트릭스 (업데이트):**

| SKIP_RAG | SKIP_TOOL | SKIP_DIRECT | 가용 경로 |
|----------|-----------|-------------|-----------|
| false    | false     | false       | rag, tool, both, direct |
| false    | false     | true        | rag, tool, both |
| false    | true      | true        | rag |
| true     | false     | true        | tool |
| true     | true      | true        | (가용 경로 없음 → fallback 필요) |

**영향 파일:**
- `app/core/config.py` — `SKIP_DIRECT: bool = True` 추가 (기본값 true: RAG 필수 경유)
- `app/workflows/main_agent/prompts/router.py` — `get_available_routes()`에 SKIP_DIRECT 반영
- `app/workflows/main_agent/nodes/router.py` — 가용 경로 1개 이하 시 LLM 호출 생략 로직
- `app/api/v1/chat.py` — SSE 스트리밍 필터 (synthesizer LLM만 전송)
- `.env.example`, `.env` — `SKIP_DIRECT=true` 추가
- `tests/test_router.py` — SKIP_DIRECT 조합 테스트 추가

### C. Rewriter 프롬프트 미세 조정

**수정 방향:**
- 대명사 해소 시 원문 구조 보존 규칙 강화
- 키워드 추가 금지 규칙 재강조

**영향 파일:**
- `app/workflows/main_agent/prompts/rewriter.py`

### D. 테스트 반영

- 프롬프트 변경에 따른 기존 테스트 assertion 수정
- SKIP_DIRECT 조합별 단위 테스트 추가

**영향 파일:**
- `tests/test_query_rewriter.py`
- `tests/test_router.py`
- `tests/test_retriever_synthesizer.py`

## Acceptance Criteria

### AC 3.3.1: Synthesizer 프롬프트 상세화

**Given** Synthesizer 시스템 프롬프트가 있을 때
**When** 프롬프트 내용을 확인하면
**Then** 답변 깊이, 문서 요약/인용 기준, 질문 유형별 답변 전략이 포함되어 있다

### AC 3.3.2: SKIP_DIRECT=true 시 RAG 필수 경유

**Given** `SKIP_DIRECT=true`로 설정되어 있을 때
**When** 어떤 질문이든 들어오면
**Then** Router가 `direct` 경로를 선택하지 않는다
**And** `rag`, `tool`, `both` 중 하나를 반환한다

### AC 3.3.3: SKIP_DIRECT=false 시 기존 동작 유지

**Given** `SKIP_DIRECT=false`로 설정되어 있을 때
**When** "안녕하세요"라고 인사하면
**Then** Router가 `direct`를 반환할 수 있다

### AC 3.3.4: Rewriter 원문 보존

**Given** Rewriter 프롬프트가 있을 때
**When** 프롬프트 내용을 확인하면
**Then** 원문 구조 보존 규칙과 키워드 추가 금지 규칙이 명확히 포함되어 있다

### AC 3.3.5: 기존 테스트 통과

**Given** 모든 변경이 완료된 후
**When** 전체 단위 테스트를 실행하면
**Then** 모든 테스트가 통과한다

## Definition of Done

- [ ] Synthesizer 프롬프트 답변 품질 가이드 강화
- [ ] `SKIP_DIRECT` 환경변수 추가 (config, router, .env.example)
- [ ] Rewriter 프롬프트 원문 보존 규칙 강화
- [ ] SKIP_DIRECT 조합별 단위 테스트 추가
- [ ] 프롬프트 변경에 따른 기존 테스트 수정
- [ ] SSE 스트리밍 필터: Router/Rewriter LLM 응답이 사용자에게 노출되지 않도록 수정
- [ ] Synthesizer 프롬프트에서 "문서에서 확인되지 않았습니다" 안내 문구 제거
- [ ] 전체 단위 테스트 통과 확인
- [ ] 수동 테스트 검증 (RAG 필수 경유 + 답변 품질)
