# 라우터 의도 분류 테스트 가이드

## 개요

Router 노드는 LLM을 사용하여 사용자 질문의 의도를 분석하고 실행 경로(`rag` / `tool` / `both` / `direct`)를 결정합니다.
LLM 응답은 비결정적이므로, 프롬프트에 **라우팅 힌트 키워드**가 내장되어 있어 테스트 시 특정 경로를 강제할 수 있습니다.

선택 가능한 경로는 SKIP 플래그에 따라 동적으로 제한됩니다. 기본 설정은 `SKIP_DIRECT=true`이므로 **`direct`는 평소 비활성**이며, 가용 경로가 1개 이하이면 LLM 호출 없이 해당 경로로 바로 진행합니다.

| `SKIP_RAG` | `SKIP_TOOL` | `SKIP_DIRECT` | 가용 경로 |
|:---:|:---:|:---:|-----------|
| false | false | false | `rag`, `tool`, `both`, `direct` |
| false | false | true (기본값) | `rag`, `tool`, `both` |
| false | true | true | `rag` |
| true | false | true | `tool` |

## 라우팅 힌트 키워드

쿼리에 아래 키워드를 포함하면 해당 경로로 라우팅됩니다.

| 키워드 | 경로 | 설명 |
|--------|------|------|
| `RAG노드사용` | `rag` | RAG(문서 검색) 경로 강제 |
| `TOOL노드사용` | `tool` | Tool(도구 실행) 경로 강제 |

> 기타 자연어 키워드("사내문서", "규정", "매뉴얼" 등)도 `rag`로, ("날씨", "계산", "API", "실시간" 등)은 `tool`로 분류되지만 LLM 판단에 의존하므로 100% 보장되지 않습니다. 위 두 키워드가 가장 결정적입니다.

`direct`를 테스트하려면 `SKIP_DIRECT=false`로 두고 일반 상식·인사·시사 질문("안녕하세요", "파이썬이란 무엇인가요?")을 보냅니다. 프롬프트는 판단이 애매하면 `rag`로 보내도록 지시되어 있습니다.

## 테스트 예시

### curl 테스트

`user_depts`는 **필수 필드**입니다. 누락하거나 빈 배열이면 422가 반환됩니다.

```bash
# RAG 경로 강제
curl -N -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "RAG노드사용 사내 규정 알려줘", "session_id": "test-1", "user_depts": ["dept-001"]}'

# Tool 경로 강제
curl -N -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "TOOL노드사용 오늘 날씨", "session_id": "test-2", "user_depts": ["dept-001"]}'
```

### 확인 방법

1. **서버 로그** — 가장 확실합니다. `LOG_LEVEL=INFO`일 때 router 노드가 structlog로 결정 결과를 남깁니다.
   ```
   router_decided route=rag available=['rag', 'tool', 'both'] query_preview=RAG노드사용 사내 규정 알려줘
   ```
   가용 경로가 1개뿐이라 LLM을 건너뛴 경우에는 `router_single_route`가 찍힙니다.

2. **LangFuse** — 트레이싱이 활성화된 경우, Router 노드의 span에서 입출력을 확인할 수 있습니다.

3. **SSE thought 이벤트** — `INCLUDE_THOUGHTS_IN_RESPONSE=true`로 설정하면 노드 진입 시 thought가 전송됩니다.
   ```
   event: thought
   data: {"content": "질문 의도를 파악했습니다."}
   ```
   ⚠ 이 문구는 `chat.py`의 `NODE_THOUGHTS`에 정의된 **노드별 고정 문구**이며, **선택된 경로를 담고 있지 않습니다.** 경로가 포함된 문구("질문 의도를 분석하여 RAG 경로를 선택했습니다.")는 `AgentState.thoughts`에만 누적되고 SSE로 나가지 않습니다. 경로 확인은 위의 서버 로그나 LangFuse를 쓰세요.

## 내부 동작

라우팅 결정 흐름:

```
query → build_router_prompt(available_routes) → LLM 응답 → _parse_route(content, available_routes) → route
```

`_parse_route()`는 LLM 응답을 다음 순서로 파싱합니다. 매칭 우선순위는 `both > tool > rag > direct`입니다.

1. 응답 전체가 `rag`, `tool`, `both`, `direct` 중 하나이면 사용. 단 **가용 경로가 아니면 기본 경로로 대체**
2. 응답에 경로명이 포함되어 있으면 위 우선순위 순으로 추출. 마찬가지로 가용하지 않으면 기본 경로로 대체
3. 어느 것도 매칭되지 않으면 기본 경로 반환

기본 경로는 `_get_default_route()`가 결정합니다. `rag`가 가용하면 `rag`, 아니면 `tool`, 그것도 아니면 `direct`입니다.

LLM 호출이 실패하면(`BusinessException` 또는 예외) 기본 경로로 fallback하며, 워크플로우는 중단되지 않습니다.

`route == "both"`이면 `graph.py::route_by_intent()`가 `["rag", "tool"]`을 반환해 retriever와 tool_executor를 fan-out으로 병렬 실행합니다. `direct`는 두 노드를 건너뛰고 synthesizer로 직행합니다.

## 관련 파일

| 파일 | 역할 |
|------|------|
| `app/workflows/main_agent/nodes/router.py` | Router 노드 함수 + `_parse_route()`, `_get_default_route()` |
| `app/workflows/main_agent/prompts/router.py` | 라우팅 프롬프트 + `get_available_routes()` (SKIP 매트릭스) |
| `app/workflows/main_agent/graph.py` | `route_by_intent()` 조건부 엣지 + fan-out |
| `tests/test_router.py` | Router 단위 테스트 (44개) |
