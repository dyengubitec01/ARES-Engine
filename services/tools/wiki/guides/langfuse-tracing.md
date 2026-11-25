# Langfuse Cross-Service Tracing 아키텍처

## 개요

TOL 서버는 에이전트 서버의 Langfuse trace에 하위 span으로 연결되어, 전체 요청 흐름을 하나의 trace 트리에서 추적할 수 있다.

## Trace 생성 조건

Langfuse trace는 **다음 조건을 모두 만족할 때만** 생성된다:

1. 요청 헤더에 `X-LF-Trace-ID`가 있을 것 (에이전트가 전달)
2. 요청 경로가 `/health`가 아닐 것
3. Langfuse 클라이언트가 설정되어 있을 것 (환경변수)
4. trace_id가 유효한 hex 형식일 것 (UUID 36자 또는 hex 32자)

조건을 만족하지 않으면 Langfuse 관련 동작 없이 서버가 정상 응답한다.

## 헤더 규격

| 헤더 | 방향 | 필수 | 설명 |
|------|------|------|------|
| `X-LF-Trace-ID` | Agent → TOL | O (tracing 시) | Langfuse trace ID (UUID 또는 32자 hex) |
| `X-LF-Parent-Id` | Agent → TOL | X | 에이전트의 parent span observation ID |
| `X-LF-Trace-ID` | TOL → Agent | O (항상) | 응답 헤더에 trace ID 반환 (자동 생성 포함) |
| `X-LF-Trace-ID-Generated` | TOL → Agent | X | 헤더 미전달 시 자동 생성 표시 (`true`) |

## Trace 계층 구조

```
Agent Trace
└─ Agent Span (X-LF-Parent-Id로 전달)
   └─ http-request (TOL root span)
      └─ llm-invoke:primary (child span)
         └─ (실패 시) llm-invoke:fast (fallback span)
```

## 동작 흐름

### 1. TraceIDMiddleware (root span 생성)

```
요청 수신
  → X-LF-Trace-ID 헤더 확인
  → 없으면: trace_id 자동 생성, Langfuse skip
  → 있으면: trace_context 구성 { trace_id, parent_span_id? }
  → Langfuse root span "http-request" 생성 (strip_as_root 래퍼 적용)
  → request.state.trace_context에 child trace_context 저장
  → 다음 미들웨어/라우터로 전달
```

### 2. Router (trace_context 전파)

```python
# src/routers/summary.py
trace_context = getattr(raw_request.state, "trace_context", None)
result = await summarize(..., trace_context=trace_context)
```

`request.state.trace_context`에서 dict를 꺼내 Service로 전달.

### 3. Service → Provider (child span 생성)

```python
# src/providers/gateway.py — invoke_with_failover()
span = create_span(
    name=f"llm-invoke:{current_role}",
    input_data={...},
    trace_context=trace_context,  # 전달받은 context
)
```

`create_span()`은 `trace_context`가 없으면 `None`을 반환 (독립 observation 방지).

## 핵심 컴포넌트

### ManagedSpan

`start_as_current_observation()`의 context manager 생명주기를 관리하는 래퍼.

```python
class ManagedSpan:
    def update(self, **kwargs): ...  # span 속성 업데이트
    def end(self): ...               # cm.__exit__() 호출 → latency 기록 + flush
```

`end()` 호출 시 context manager가 정상 종료되어 latency 기록과 output flush가 보장된다.

### strip_as_root

Langfuse SDK v3에서 `start_as_current_observation(trace_context=...)`를 호출하면 내부적으로 `AS_ROOT=True`가 설정되어 원래 trace name이 덮어쓰여진다. `strip_as_root` 래퍼가 이를 `False`로 재설정하여 방지한다.

```python
# src/middleware/langfuse.py
@contextmanager
def strip_as_root(cm):
    with cm as span:
        span._otel_span.set_attribute("langfuse.internal.as_root", False)
        yield span
```

### create_span / create_generation 가드

`trace_context`가 없으면 즉시 `None`을 반환하여 독립 observation이 생성되지 않도록 한다.

```python
def create_span(name, ..., trace_context=None):
    if not trace_context:
        return None       # 독립 observation 방지
    ...
```

## trace_context 전파 경로

```
TraceIDMiddleware
  → request.state.trace_context = { trace_id, parent_span_id }
    → Router (summary_endpoint)
      → Service (summarize)
        → Provider (invoke_with_failover)
          → create_span(trace_context=...)
```

## 에이전트 연동

에이전트 서버에서 TOL을 호출할 때:

```python
import httpx

headers = {
    "X-LF-Trace-ID": langfuse_trace_id,         # 필수
    "X-LF-Parent-Id": current_span_id,           # 선택
    "X-TOL-Scope": "agent",
}
response = await client.post(
    "http://tol-server:8007/v1/summary",
    json={"history": [...]},
    headers=headers,
)
```

## 관련 파일

| 파일 | 역할 |
|------|------|
| `src/middleware/trace_id.py` | TraceIDMiddleware — root span 생성, trace_context 구성 |
| `src/middleware/langfuse.py` | ManagedSpan, create_span, strip_as_root, create_generation |
| `src/routers/summary.py` | request.state.trace_context 추출 |
| `src/services/summary.py` | trace_context 전달 |
| `src/providers/gateway.py` | invoke_with_failover — child span 생성 |
| `tests/test_trace_id.py` | trace 관련 테스트 (22건) |
| `tests/test_langfuse.py` | span/generation 테스트 (18건) |
