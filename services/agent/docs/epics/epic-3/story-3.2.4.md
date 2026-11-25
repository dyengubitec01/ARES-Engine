# Story 3.2.4: LLM 호출 시 max_tokens / temperature 환경변수 설정 추가

## Enhancement Story

**Parent:** Epic 3 (답변 품질 + RAG 검색 안정화)
**Type:** Enhancement
**Branch:** feat/llm-generation-params

## 배경

현재 `ChatOpenAI` 인스턴스 생성 시 `max_tokens`와 `temperature`를 지정하지 않아 LLM 서버 기본값에 의존하고 있음.

### 문제점

1. **max_tokens 미설정:** LLM이 불필요하게 긴 응답을 생성하거나, 서버 기본값이 너무 작으면 응답이 중간에 잘릴 수 있음
2. **temperature 미설정:** 분류(router)와 생성(synthesizer) 작업이 동일한 temperature로 동작하여, router의 비결정적 응답이나 synthesizer의 지나치게 보수적인 응답 발생 가능
3. **운영 제어 불가:** 배포 후 환경변수로 생성 파라미터를 조정할 수 없어, 튜닝 시 코드 변경 및 재배포 필요

### 현재 상태 (`llm_factory.py:get_llm()`)

```python
llm = ChatOpenAI(
    base_url=base_url,
    model=model_name,
    api_key=app_settings.LLM_API_KEY,
    timeout=app_settings.LLM_TIMEOUT,
    # max_tokens → 없음 (서버 기본값)
    # temperature → 없음 (서버 기본값)
)
```

## 수정 항목

### A. config.py에 환경변수 추가

`app/core/config.py`의 `Settings` 클래스에 다음 필드 추가:

- `LLM_MAX_TOKENS: int = 2048` — LLM 응답 최대 토큰 수
- `LLM_TEMPERATURE: float = 0.6` — LLM 생성 temperature

### B. llm_factory.py의 get_llm()에 파라미터 전달

`ChatOpenAI` 생성 시 `max_tokens`와 `temperature`를 settings에서 가져와 전달:

```python
llm = ChatOpenAI(
    base_url=base_url,
    model=model_name,
    api_key=app_settings.LLM_API_KEY,
    timeout=app_settings.LLM_TIMEOUT,
    max_tokens=app_settings.LLM_MAX_TOKENS,      # 기본값: 2048
    temperature=app_settings.LLM_TEMPERATURE,    # 기본값: 0.6
)
```

### C. 테스트 수정

- `tests/test_config.py` — 신규 설정 필드 기본값 검증
- `tests/test_llm_factory.py` — `ChatOpenAI` 생성 시 `max_tokens`, `temperature` 전달 검증

**영향 파일:**
- `app/core/config.py`
- `app/core/llm_factory.py`
- `.env.example`
- `tests/test_config.py`
- `tests/test_llm_factory.py`

## Acceptance Criteria

### AC 3.2.4.1: 환경변수 기본값

**Given** 환경변수 `LLM_MAX_TOKENS`, `LLM_TEMPERATURE`가 설정되지 않았을 때
**When** Settings를 로드하면
**Then** `LLM_MAX_TOKENS`는 `2048`, `LLM_TEMPERATURE`는 `0.6`이 기본값이다

### AC 3.2.4.2: 환경변수 오버라이드

**Given** `LLM_MAX_TOKENS=1024`, `LLM_TEMPERATURE=0.3`으로 환경변수를 설정했을 때
**When** Settings를 로드하면
**Then** 해당 값이 설정에 반영된다

### AC 3.2.4.3: ChatOpenAI에 파라미터 전달

**Given** Settings에 `LLM_MAX_TOKENS=2048`, `LLM_TEMPERATURE=0.6`이 설정되어 있을 때
**When** `llm_factory.get_llm("primary")`를 호출하면
**Then** 생성된 `ChatOpenAI` 인스턴스에 `max_tokens=2048`, `temperature=0.6`이 전달된다

### AC 3.2.4.4: 기존 테스트 통과

**Given** 신규 설정이 추가된 후
**When** 전체 단위 테스트를 실행하면
**Then** 모든 테스트가 통과한다

## Definition of Done

- [ ] `app/core/config.py`에 `LLM_MAX_TOKENS`, `LLM_TEMPERATURE` 필드 추가
- [ ] `app/core/llm_factory.py`의 `get_llm()`에 `max_tokens`, `temperature` 전달
- [ ] `tests/test_config.py`에 기본값 검증 테스트 추가
- [ ] `tests/test_llm_factory.py`에 파라미터 전달 검증 테스트 추가
- [ ] 전체 단위 테스트 통과 확인
