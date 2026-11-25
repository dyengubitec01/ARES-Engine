# LangFuse 트레이싱 아키텍처

## 개요

Agent Server는 LangFuse SDK v3를 사용하여 워크플로우 전체를 하나의 **Trace**로 기록합니다.
각 노드 실행은 자동으로 **Span(Observation)**이 되고, 외부 서비스(RAG/Tool Server)에도 trace가 전파됩니다.

## Trace 계층 구조

하나의 채팅 요청이 LangFuse에서 어떻게 보이는지:

```
Trace (name="agent", session_id="abc-123")
├── Span: rewriter
│   └── Generation: LLM call (query rewriting)
├── Span: router
│   └── Generation: LLM call (intent classification)
├── Span: retriever                          ← X-LF-Trace-ID 헤더로 RAG 서버에 전파
│   └── (RAG 서버 내부 span들이 여기 하위에 연결됨)
├── Span: tool_executor                      ← X-LF-Trace-ID 헤더로 Tool 서버에 전파
│   └── (Tool 서버 내부 span들이 여기 하위에 연결됨)
└── Span: synthesizer
    └── Generation: LLM call (response generation)
```

> `route=both`인 경우 retriever와 tool_executor가 병렬로 실행되며, 각각 별도 span으로 기록됩니다.

## Trace 생성 흐름

### 1단계: Trace 시작 (API 레이어)

`POST /v1/chat` 요청이 들어오면:

```python
# app/api/v1/chat.py — stream_workflow()
config = tracing.get_langfuse_config(
    session_id=request.session_id,    # → langfuse_session_id
    user_id=request.user_id,          # → langfuse_user_id
    tags=["chat", "streaming"],
    metadata={"query_preview": ..., "history_length": ...},
)

# LangGraph에 config 전달 → LangFuse CallbackHandler가 자동으로 trace 생성
async for event in graph.astream_events(initial_state, config=config, version="v2"):
    ...
```

`TracingManager.get_langfuse_config()`가 하는 일:
1. `CallbackHandler(update_trace=True)` 인스턴스 생성
2. `config["callbacks"]`에 handler 등록
3. `config["metadata"]`에 `langfuse_session_id`, `langfuse_user_id`, `langfuse_tags` 설정

### 2단계: 노드별 Span 자동 기록

LangGraph가 각 노드를 실행할 때 LangFuse CallbackHandler가 자동으로:
- 노드 시작 → Span 시작 (on_chain_start)
- 노드 내 LLM 호출 → Generation span 생성 (on_llm_start/on_llm_end)
- 노드 종료 → Span 종료 (on_chain_end)

별도 코드 없이 LangChain/LangGraph 이벤트가 LangFuse에 자동 기록됩니다.

### 3단계: Cross-Service 전파 (retriever, tool_executor)

외부 서비스 호출 시, 현재 노드의 trace 정보를 HTTP 헤더로 전달합니다.

```python
# app/workflows/shared/tracing_utils.py
trace_ctx = extract_trace_context(config)
# → TraceContext(trace_id="abc-...", observation_id="obs-...")
```

```python
# app/clients/rag_client.py (RealRAGClient)
headers = {}
if trace_id:
    headers["X-LF-Trace-ID"] = trace_id        # 같은 trace에 합류
if observation_id:
    headers["X-LF-Parent-Id"] = observation_id  # 이 span의 하위로 연결
```

## 헤더 규격

| 헤더 | 값 | 목적 |
|------|------|------|
| `X-LF-Trace-ID` | LangFuse trace ID | 수신 서버가 같은 trace에 합류 |
| `X-LF-Parent-Id` | LangFuse observation ID | 수신 서버의 span이 호출 노드의 하위에 연결 |
| `X-TOL-Scope` | `"agent"` | Tool 서버 전용 — 호출자 식별 |

> RAG/Tool 서버가 이 헤더를 읽어 자체 LangFuse trace에 활용해야 cross-service 연결이 완성됩니다.

## trace_id 추출 메커니즘

`extract_trace_context(config)`의 내부 동작:

```
RunnableConfig
  └── callbacks (CallbackManager)
        ├── handlers[] → LangFuse handler 찾기
        │     └── handler.last_trace_id → trace_id 추출
        └── parent_run_id → handler.runs[parent_run_id].id → observation_id 추출
```

SDK v2/v3 모두 지원:
- v2: `handler.get_trace_id()` 또는 `handler.trace_id`
- v3: `handler.last_trace_id`

## LangFuse 메타데이터 매핑

| 매개변수 | config key | LangFuse 필드 |
|----------|------------|---------------|
| `session_id` | `langfuse_session_id` | Session |
| `user_id` | `langfuse_user_id` | User |
| `tags` | `langfuse_tags` | Tags (필터링용) |
| `run_name` | `run_name` | Trace name |
| `metadata` | config metadata에 병합 | Metadata |

## 활성화/비활성화

```bash
# .env
LANGFUSE_TRACING_ENABLED=true        # false면 전체 비활성화 (에러 없음)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000   # 로컬 LangFuse 서버
```

비활성화 상태에서:
- `get_callback_handler()` → `None` 반환
- `get_langfuse_config()` → 빈 dict `{}` 반환 (callbacks 없음)
- 워크플로우는 정상 실행되고, trace만 기록되지 않음

## 로컬 LangFuse 서버 실행

```bash
docker compose -f docker-compose.dev.yaml up -d
# → http://localhost:3000 에서 LangFuse UI 접근
```

## 관련 파일

| 파일 | 역할 |
|------|------|
| `app/core/tracing.py` | `TracingManager` — 초기화, handler/config 생성 |
| `app/workflows/shared/tracing_utils.py` | `extract_trace_context()` — trace_id/observation_id 추출 |
| `app/api/v1/chat.py` | Trace 시작점 (stream_workflow) |
| `app/workflows/main_agent/graph.py` | Trace 시작점 (run_workflow) |
| `app/clients/rag_client.py` | X-LF 헤더 전송 (RAG 서버) |
| `app/clients/tool_client.py` | X-LF 헤더 전송 (Tool 서버) |
| `tests/test_tracing.py` | TracingManager 단위 테스트 (11개) |
