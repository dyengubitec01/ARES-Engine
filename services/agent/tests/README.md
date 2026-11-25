# Agent Server Tests

## 테스트 구조

```
tests/
├── README.md                          # 이 문서
├── conftest.py                        # 공통 fixtures
├── __init__.py
│
├── test_chat.py                       # Chat API, SSE 포맷 (17)
├── test_config.py                     # 설정 관리 (17)
├── test_exception_handling.py         # 예외 처리, 에러 코드 (34)
├── test_health_models.py              # Health/Models API (14)
├── test_llm_factory.py                # LLM 팩토리, Failover (16)
├── test_query_rewriter.py             # Query Rewriter 노드 (24)
├── test_rag_client.py                 # RAG 클라이언트 (21)
├── test_retriever_synthesizer.py      # Retriever/Synthesizer 노드 (26)
├── test_router.py                     # Router 노드 - 의도 분류 (18)
├── test_tool_client.py                # Tool 클라이언트 (30)
├── test_tool_executor.py              # Tool Executor 노드 (14)
├── test_tracing.py                    # LangFuse 트레이싱 (11)
├── test_workflow_graph.py             # 워크플로우 그래프 (22)
│                                      # ── 단위: 301개 ──
└── integration/                       # 통합 테스트 (실제 서버 필요)
    ├── conftest.py                    # skip 조건, 서버 fixtures
    ├── __init__.py
    ├── test_chat_integration.py       # Chat API E2E (10)
    ├── test_langfuse_integration.py   # LangFuse 트레이싱 + 헤더 (9)
    └── test_workflow_routes.py        # rag/tool/both 라우트 (5)
                                       # ── 통합: 24개 ──
```

**총 325개** (단위 301 + 통합 24)

## 실행 방법

```bash
# 단위 테스트 (통합 자동 제외)
uv run pytest

# 통합 테스트 (LLM, LangFuse, RAG/Tool 서버 필요 — 없으면 자동 스킵)
uv run pytest tests/integration/ -m integration -v

# 커버리지
uv run pytest --cov=app --cov-report=term-missing
```

전체 테스트 인벤토리와 상세 설명은 [wiki/tests.md](../wiki/tests.md) 참조.

## 테스트 작성 가이드

### 명명 규칙

- 클래스: `Test{기능명}` (예: `TestFormatSSE`)
- 함수: `test_{동작}_{조건}` (예: `test_format_sse_thought`)

### Mock 사용

- **단위 테스트**: Mock 적극 사용 (`unittest.mock.patch`, `AsyncMock`)
- **통합 테스트**: Mock 사용 금지 (실제 서버 연결)

### 통합 테스트 Skip 조건

`tests/integration/conftest.py`에 정의:

| 데코레이터 | 스킵 조건 |
|-----------|----------|
| `@skip_no_llm` | LLM 서버 미연결 |
| `@skip_no_langfuse` | LangFuse 미설정 |
| `@skip_no_rag` | RAG 서버 미연결 |
| `@skip_no_tool` | Tool 서버 미연결 |
