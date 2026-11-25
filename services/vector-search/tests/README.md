# RAG Search Server Tests

## 테스트 구조

```
tests/
├── README.md                          # 이 문서
├── conftest.py                        # 공통 fixtures (--run-integration 옵션)
├── __init__.py
│
├── test_config.py                     # 설정 관리 (9)
├── test_embedding.py                  # 임베딩 어댑터 (14)
├── test_exceptions.py                 # 예외 처리, 에러 코드 (15)
├── test_health.py                     # Health check (3)
├── test_monitoring.py                 # Langfuse 트레이싱 (35)
├── test_qdrant_adapter.py             # Qdrant 어댑터 (15)
├── test_reranker_adapter.py           # 리랭커 어댑터 (19)
├── test_responses.py                  # 표준 응답 규격 (17)
├── test_search.py                     # 검색 서비스 + 엔드포인트 (35)
│                                      # ── 단위: 162개 ──
└── test_search_integration.py         # 실서버 통합 (3, --run-integration 필요)
                                       # ── 통합: 3개 ──
```

**총 165개** (단위 162 + 통합 3)

## 실행 방법

```bash
# 단위 테스트 (통합 자동 제외)
pytest

# 통합 테스트 (Embedding API, Qdrant 필요 — 없으면 자동 스킵)
pytest --run-integration -v

# 커버리지
pytest --cov=app --cov-report=term-missing
```

전체 테스트 인벤토리와 상세 설명은 [wiki/tests.md](../wiki/tests.md) 참조.
