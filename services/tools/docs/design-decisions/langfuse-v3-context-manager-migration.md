# Langfuse SDK v3 Context Manager 리팩터링

> 작성일: 2026-02-03
> 프로젝트: TOL (Tools-REST-API)
> 선행 문서: [Trace-ID ContextVar 전파 패턴](./trace-id-contextvar-propagation.md)

---

## 1. 도입 배경

### 1.1 이전 아키텍처 (ContextVar 이중 구조)

[trace-id-contextvar-propagation.md](./trace-id-contextvar-propagation.md)에서 설계한 구조는 두 개의 ContextVar를 사용했다:

```
trace_id_var (str)          — Trace-ID 문자열 (TraceIDMiddleware에서 관리)
_current_trace (Langfuse)   — Langfuse trace 객체 (langfuse.py에서 관리)
```

흐름은 다음과 같았다:

```
TraceIDMiddleware.dispatch()
  │
  ├─ trace_id_var.set("agent-trace-001")
  ├─ call_next(request)
  │    │
  │    └─ 라우터/서비스에서 create_trace() 호출  ← ★ 여기가 문제
  │         │
  │         ├─ get_trace_id() → "agent-trace-001"
  │         ├─ client.start_span(trace_context=...)
  │         └─ _current_trace.set(span)
  │              │
  │              ├─ create_span() → _current_trace.get().start_span(...)
  │              └─ create_generation() → _current_trace.get().start_generation(...)
  │
  └─ trace_id_var.reset(token)
```

### 1.2 문제: `create_trace()`를 아무도 호출하지 않음

`_current_trace`에 값을 넣는 유일한 함수는 `create_trace()`였다. 그런데 프로덕션 코드에서 이 함수를 호출하는 곳이 **없었다**:

- 미들웨어(`trace_id.py`)는 `trace_id_var`만 설정하고 `create_trace()`를 호출하지 않음
- 라우터/서비스 계층도 `create_trace()`를 호출하지 않음
- 별도의 Langfuse 미들웨어도 존재하지 않음

결과:

```python
# langfuse.py — 이전 코드
def create_span(name, input_data=None, metadata=None):
    trace = get_current_trace()  # ← _current_trace.get()
    if not trace:
        return None              # ← 프로덕션에서 항상 여기 도달
    return trace.start_span(...) # ← 도달 불가
```

`_current_trace`가 항상 `None`이므로 `create_span()` 7곳, `create_generation()` 전부 `None` 반환 → **Langfuse 트레이싱 완전 미동작**.

### 1.3 왜 별도 미들웨어를 만들지 않았는가

`create_trace()`를 호출하는 별도 `LangfuseMiddleware`를 추가하는 방법도 있었다:

```python
# 고려했으나 채택하지 않은 접근
class LangfuseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        create_trace("http-request")
        response = await call_next(request)
        reset_trace()
        return response
```

**문제점:** Starlette의 미들웨어 스택 구조상, exception handler는 미들웨어 바깥에서 실행된다. `LangfuseMiddleware`의 `with` 블록이 끝난 후에 `generic_exception_handler`가 호출되므로, exception handler 안의 `create_span("graceful-degradation")`이 OTEL context 밖에서 실행되어 root span 하위로 nesting되지 않는다.

`TraceIDMiddleware` 안에서 Langfuse context manager를 사용해야 `call_next()`에서 발생한 예외를 catch하는 시점에도 여전히 OTEL context 안이므로, exception handler의 `create_span()`도 root span 하위로 정상 nesting된다.

---

## 2. 새로운 아키텍처 (OTEL Auto-Nesting)

### 2.1 핵심 변경

ContextVar 이중 구조를 제거하고, Langfuse SDK v3의 **OTEL context manager**를 사용한다:

| 항목 | 이전 | 이후 |
|------|------|------|
| Root span 설정 | `create_trace()` (수동 호출, 누락됨) | `start_as_current_observation()` (미들웨어에서 자동) |
| 부모-자식 연결 | `_current_trace.get().start_span()` (수동) | OTEL auto-nesting (자동) |
| Child span 생성 | `trace.start_span()` | `client.start_observation()` |
| 상태 관리 | `_current_trace` ContextVar (수동 set/reset) | OTEL context (`with` 블록 자동 관리) |

### 2.2 제거된 것

```python
# langfuse.py에서 제거
_current_trace: ContextVar[Any]       # Langfuse trace ContextVar
def create_trace(name, metadata)      # root trace 생성
def get_current_trace()               # 현재 trace 조회
def reset_trace()                     # trace 초기화

# import 정리
from contextvars import ContextVar
from langfuse.types import TraceContext  # trace_id.py로 이동
from src.middleware.trace_id import get_trace_id
```

### 2.3 역할 분리

```
┌─────────────────────────────────────────────────────────┐
│  TraceIDMiddleware (trace_id.py)                        │
│  ─ trace_id 추출/생성 (ContextVar)                      │
│  ─ Langfuse root span 설정 (OTEL context manager)       │
│  ─ 요청 전체의 생명주기 관리                               │
└─────────────────────────────────────────────────────────┘
                          │
                          │  OTEL context 자동 전파
                          ▼
┌─────────────────────────────────────────────────────────┐
│  create_span() / create_generation() (langfuse.py)      │
│  ─ client.start_observation() 호출만 담당                 │
│  ─ 부모가 누군지 몰라도 됨 (OTEL이 자동 연결)              │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 전체 요청 플로우

### 3.1 에이전트가 유효 UUID trace-id를 전달한 경우

```
에이전트 서버                              TOL 서버
─────────────                         ────────────
POST /v1/summary
Headers:
  X-LF-Trace-ID: 550e8400-e29b-41d4-a716-446655440000

  ──→  TraceIDMiddleware.dispatch()
         │
         ├─ (1) 헤더에서 trace_id 추출
         ├─ (2) trace_id_var.set("550e8400-e29b-...")   ← ContextVar (기존 유지)
         │
         ▼
       _handle_request()
         │
         ├─ (3) get_langfuse_client() → client 존재
         ├─ (4) trace_id_hex = "550e8400e29b41d4a716446655440000"
         │       (하이픈 제거, 32자리 hex 검증 통과)
         │
         ├─ (5) with client.start_as_current_observation(    ← ★ OTEL context 시작
         │         as_type="span",
         │         name="http-request",
         │         trace_context={"trace_id": trace_id_hex},
         │         input={"method": "POST", "path": "/v1/summary"},
         │       ) as root_span:
         │       ┌──────────────────────────────────────────┐
         │       │  이 블록 안의 모든 start_observation()   │
         │       │  호출이 root_span의 child로 자동 nesting  │
         │       └──────────────────────────────────────────┘
         │           │
         │           ├─ (6) call_next(request)
         │           │       │
         │           │       ▼
         │           │   라우터 → summarize() 서비스
         │           │       │
         │           │       ├─ create_span("tool-scoping")      ← child #1
         │           │       │   └─ client.start_observation(as_type="span")
         │           │       │
         │           │       ├─ create_span("llm-invoke:primary") ← child #2
         │           │       │   └─ client.start_observation(as_type="span")
         │           │       │
         │           │       └─ create_span("proxy-request")     ← child #3
         │           │           └─ client.start_observation(as_type="span")
         │           │
         │           ├─ (7) root_span.update(output={"status_code": 200})
         │           └─ response 반환
         │
         ├─ (8) trace_id_var.reset(token)
         ├─ (9) 응답 헤더: X-LF-Trace-ID: 550e8400-e29b-...
         └─ response 반환
```

### 3.2 trace-id 없이 요청한 경우 (자동 생성)

```
외부 클라이언트                            TOL 서버
─────────────                         ────────────
POST /v1/summary
Headers:
  (X-LF-Trace-ID 없음)

  ──→  TraceIDMiddleware.dispatch()
         │
         ├─ (1) 헤더에 trace_id 없음 감지
         ├─ (2) generate_trace_id() → "f47ac10b-58cc-4372-a567-0e02b2c3d479"
         ├─ (3) is_generated = True
         │
         ▼
       _handle_request()
         │
         ├─ (4) trace_id_hex = "f47ac10b58cc4372a5670e02b2c3d479"
         │       (UUID이므로 32자리 hex 검증 통과)
         │
         ├─ (5) start_as_current_observation(...)  ← root span 생성
         │       │
         │       └─ (이하 3.1과 동일한 auto-nesting 플로우)
         │
         ├─ (6) 응답 헤더:
         │       X-LF-Trace-ID: f47ac10b-58cc-4372-a567-0e02b2c3d479
         │       X-LF-Trace-ID-Generated: true
         └─ response 반환
```

### 3.3 예외 발생 시 (exception handler도 OTEL context 안)

```
       _handle_request()
         │
         ├─ start_as_current_observation(...) as root_span:
         │       │
         │       ├─ call_next(request)
         │       │       │
         │       │       ▼
         │       │   라우터에서 LLMProviderError 발생
         │       │       │
         │       │       └─ 예외가 미들웨어까지 전파
         │       │
         │       ├─ except Exception:
         │       │       │
         │       │       ├─ root_span.update(
         │       │       │     output={"error": "LLMProviderError"},
         │       │       │     level="ERROR",
         │       │       │ )
         │       │       │
         │       │       └─ generic_exception_handler(request, exc)
         │       │               │
         │       │               └─ create_span("graceful-degradation")
         │       │                   └─ client.start_observation(...)
         │       │                       ↑ 여전히 root_span의 OTEL context 안
         │       │                       ↑ → root_span의 child로 자동 nesting
         │       │
         │       └─ with 블록 종료 → OTEL context 해제
```

이것이 별도 `LangfuseMiddleware`를 만들지 않은 이유이다. 예외 처리까지 root span의 `with` 블록 안에서 수행되므로, exception handler의 `create_span()`도 정상적으로 child span이 된다.

### 3.4 비-hex trace-id 또는 Langfuse 미설정 시

```
       _handle_request()
         │
         ├─ get_langfuse_client() → None?
         │    └─ Yes → call_next() 직접 호출 (Langfuse 없이)
         │
         ├─ trace_id_hex가 32자리 hex가 아닌 경우?
         │    └─ Yes → call_next() 직접 호출 (Langfuse 없이)
         │         (예: "custom-trace-id-456" → 하이픈 제거 후 hex 검증 실패)
         │
         └─ 두 조건 모두 통과 → start_as_current_observation()으로 진행
```

`start_as_current_observation()`은 trace_id를 `int(trace_id, 16)`으로 파싱하므로, 유효한 hex가 아니면 `ValueError`가 발생한다. 이를 방지하기 위해 `re.fullmatch(r"[0-9a-f]{32}", trace_id_hex)` 검증을 선행한다.

---

## 4. 파일 구조 및 책임

```
src/
├─ middleware/
│   ├─ __init__.py          # 패키지 export (create_trace 등 제거됨)
│   ├─ trace_id.py          # TraceIDMiddleware + _handle_request (root span)
│   └─ langfuse.py          # create_span, create_generation, flush, client
│
├─ exceptions/
│   └─ handlers.py          # create_span 호출 4곳
│       ├─ graceful_degradation_handler    → create_span("graceful-degradation")
│       ├─ invalid_scope_handler           → create_span("invalid-scope")
│       ├─ external_api_error_handler      → create_span("external-api-error")
│       └─ generic_exception_handler       → create_span("unhandled-exception")
│
├─ providers/
│   └─ gateway.py           # create_span 호출 1곳
│       └─ invoke_with_failover            → create_span("llm-invoke:{role}")
│
└─ services/
    ├─ proxy.py             # create_span 호출 1곳
    │   └─ proxy_request                   → create_span("proxy-request")
    └─ scoping.py           # create_span 호출 1곳
        └─ get_tools_for_scope             → create_span("tool-scoping")
```

### 4.1 호출처 7곳의 패턴

모든 호출처가 동일한 guard 패턴을 사용한다:

```python
span = create_span("span-name", input_data={...})
if span:
    span.update(output={...})
```

- `create_span()`이 `None`을 반환하면 (Langfuse 미설정 등) 아무 일도 일어나지 않음
- 각 호출처는 root span이 누구인지, OTEL context가 존재하는지 알 필요 없음
- 비즈니스 로직에 Langfuse 의존성이 침투하지 않는 구조

---

## 5. Langfuse 대시보드에서 보이는 결과

### 5.1 정상 요청

```
Trace: 550e8400e29b41d4a716446655440000
└─ span: http-request                    ← root (TraceIDMiddleware)
   ├─ input:  {"method": "POST", "path": "/v1/summary"}
   ├─ output: {"status_code": 200}
   │
   ├─ span: tool-scoping                 ← child (scoping.py)
   ├─ span: llm-invoke:primary           ← child (gateway.py)
   └─ span: proxy-request                ← child (proxy.py)
```

### 5.2 예외 발생 요청

```
Trace: 550e8400e29b41d4a716446655440000
└─ span: http-request                    ← root (level=ERROR)
   ├─ input:  {"method": "POST", "path": "/v1/summary"}
   ├─ output: {"error": "LLMProviderError"}
   │
   ├─ span: llm-invoke:primary           ← child (실패한 호출)
   └─ span: graceful-degradation         ← child (exception handler)
```

### 5.3 Langfuse 미설정 환경

Langfuse 환경변수가 없으면 `get_langfuse_client()`가 `None`을 반환하고, 모든 `create_span()`도 `None`을 반환한다. 애플리케이션 동작에는 영향 없음.

---

## 6. trace_id 하이픈 제거 (`replace("-", "")`) 결정

### 6.1 왜 `Langfuse.create_trace_id(seed=...)`를 사용하지 않는가

Langfuse SDK에는 `create_trace_id(seed=...)` 메서드가 있지만, 이 메서드는 입력값을 **해시**하여 다른 값을 생성한다:

```python
# 예시
client.create_trace_id(seed="550e8400-e29b-41d4-a716-446655440000")
# → "a1b2c3d4e5f6..." (원본과 전혀 다른 값)
```

이렇게 되면 에이전트가 보낸 `X-LF-Trace-ID` 헤더 값과 Langfuse 대시보드의 trace ID가 달라져서 추적 연관성이 상실된다.

### 6.2 채택한 방법

```python
trace_id_hex = trace_id.replace("-", "")
# "550e8400-e29b-41d4-a716-446655440000"
# → "550e8400e29b41d4a716446655440000" (원본 보존, 형식만 변환)
```

UUID의 하이픈만 제거하여 Langfuse가 요구하는 32자리 lowercase hex 형식으로 변환한다. 원본 값이 보존되므로 `X-LF-Trace-ID` 헤더와 Langfuse trace ID 간 1:1 매핑이 유지된다.

---

## 7. 관련 문서

- [Trace-ID ContextVar 전파 패턴](./trace-id-contextvar-propagation.md) — 이전 아키텍처 (본 문서의 선행 문서)
- [TECH_SPEC 4장: 관측 가능성 및 Trace-ID 전략](../TECH_SPEC.md)
- [PRD UJ-03: 연속적 관측](../prd.md)
- [Langfuse SDK v3 Tracing 문서](https://langfuse.com/docs/tracing)
