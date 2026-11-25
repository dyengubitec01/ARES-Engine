# TOL Server Tests

## 테스트 구조

```
tests/
├── README.md                          # 이 문서
├── __init__.py
│
├── test_config.py                     # YAML/ENV 설정 로더 (16)
├── test_models.py                     # Role-Based 모델 매핑, fallback 체인 (22)
├── test_prompt_engine.py              # 프롬프트 템플릿 렌더링 (12)
├── test_trace_id.py                   # Trace-ID 미들웨어, Langfuse root span (22)
├── test_langfuse.py                   # create_span, create_generation, ManagedSpan (18)
├── test_langfuse_e2e.py               # Langfuse 실환경 연결 — E2E (2)
├── test_provider.py                   # GatewayProvider, invoke, failover (36)
├── test_graceful_degradation.py       # LLM 체인 소진 시 503 응답 (5)
├── test_summary_endpoint.py           # POST /v1/summary 라우터 + 서비스 (26)
├── test_scoping.py                    # Scope 필터링, InvalidScopeError (17)
├── test_tools_endpoint.py             # GET /v1/tools, OpenAI Spec 응답 (15)
├── test_proxy_service.py              # 외부 API 프록시, 재시도, Langfuse span (27)
└── test_catch_all_handler.py          # catch-all 예외 핸들러 (2)
                                       # ── 총 218개 ──
```

**총 218개** 단위 테스트, 13개 파일.

## 실행 방법

```bash
# 전체 단위 테스트
pytest tests/

# 상세 출력
pytest tests/ -v

# 특정 파일
pytest tests/test_trace_id.py -v

# 특정 클래스
pytest tests/test_trace_id.py::TestTraceIDMiddleware -v

# 특정 테스트 함수
pytest tests/test_trace_id.py::TestTraceIDMiddleware::test_auto_generates_trace_id -v

# 패턴 필터
pytest tests/ -k "test_trace"

# 커버리지
pytest tests/ --cov=src --cov-report=term-missing

# 짧은 traceback
pytest tests/ --tb=short

# E2E 테스트 (Langfuse 서버 필요 — LANGFUSE_PUBLIC_KEY 미설정 시 자동 스킵)
pytest tests/test_langfuse_e2e.py -v
```

전체 테스트 인벤토리와 상세 설명은 [wiki/tests.md](../wiki/tests.md) 참조.

## 테스트 작성 가이드

### 명명 규칙

- 클래스: `Test{기능명}` (예: `TestCreateSpan`)
- 함수: `test_{동작}_{조건}` (예: `test_create_span_without_trace_context_returns_none`)

### Mock 사용

- **단위 테스트**: Mock 적극 사용 (`unittest.mock.patch`, `AsyncMock`, `respx`)
- **E2E 테스트**: Mock 사용 금지 (실제 Langfuse 서버 연결)

### E2E 테스트 Skip 조건

| 조건 | 스킵 기준 |
|------|----------|
| Langfuse 서버 | `LANGFUSE_PUBLIC_KEY` 환경변수 미설정 시 스킵 |
