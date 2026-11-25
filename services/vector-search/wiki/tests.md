# 테스트 문서

## 개요

RAG Search Server의 테스트 문서입니다.

- **테스트 프레임워크**: pytest, pytest-asyncio
- **총 테스트 수**: 226개 (단위) + 3개 (통합, 별도 실행) = **229개**
- **Python 버전**: 3.11+
- **비동기 모드**: `asyncio_mode = "auto"`

## 실행 방법

### 단위 테스트

```bash
# 전체 단위 테스트 실행 (통합 테스트 자동 제외)
pytest

# 상세 출력
pytest -v

# 특정 파일 실행
pytest tests/test_search.py -v

# 특정 클래스 실행
pytest tests/test_search.py::TestSearchService -v

# 특정 테스트 함수 실행
pytest tests/test_search.py::TestSearchService::test_search_returns_expected_structure -v

# 커버리지 포함 실행
pytest --cov=app --cov-report=term-missing

# HTML 커버리지 리포트 생성
pytest --cov=app --cov-report=html
# → htmlcov/index.html 에서 확인
```

### 통합 테스트

통합 테스트는 실제 임베딩 API(BGE-M3)와 Qdrant 서버가 필요합니다.
서버가 없으면 자동으로 스킵됩니다.

```bash
# 통합 테스트 포함 실행
pytest --run-integration -v
```

---

## 단위 테스트 파일 목록

| 파일 | 테스트 수 | 대상 모듈 |
|------|----------|----------|
| test_config.py | 14 | 설정 관리 + `.env.{APP_ENV}` 동적 로딩 |
| test_embedding.py | 14 | 임베딩 어댑터 (Mock + 실제) |
| test_exceptions.py | 15 | 예외 클래스 + 글로벌 핸들러 |
| test_health.py | 3 | Health check |
| test_main_startup.py | 5 | startup Hybrid full-text index 검증 |
| test_monitoring.py | 35 | Langfuse 트레이싱 |
| test_qdrant_adapter.py | 37 | Qdrant 어댑터 (dense / full-text / index / parent) |
| test_reranker_adapter.py | 19 | 리랭커 어댑터 |
| test_responses.py | 17 | 표준 응답 규격 |
| test_search.py | 67 | 검색 서비스 + RRF + Hybrid + parent 확장 + 엔드포인트 |
| **합계** | **226** | |

## 통합 테스트 파일 목록

| 파일 | 테스트 수 | 대상 | 필요 서버 |
|------|----------|------|----------|
| test_search_integration.py | 3 | 검색 파이프라인 E2E | Embedding API, Qdrant |
| **합계** | **3** | | |

### 테스트 인프라 (`tests/conftest.py`)

| 항목 | 설명 |
|------|------|
| `app` fixture | `create_app()` 후 `SearchService`에 Mock 어댑터(Embedding/VectorStore/Reranker)를 주입한 테스트용 FastAPI 앱 |
| `--run-integration` 옵션 | `pytest_addoption`으로 등록. 미지정 시 `@pytest.mark.integration` 테스트를 `pytest_collection_modifyitems`에서 자동 skip |

> 참고: Mock 어댑터는 **테스트에서만** `app` fixture를 통해 주입된다. 운영 `create_app()`은 `APP_ENV`와 무관하게 항상 실제 어댑터(EmbeddingAdapter, QdrantAdapter, RerankerAdapter)를 주입한다(`test_search.py::TestDIBinding` 참조).

---

## 테스트 상세

### 1. test_config.py (설정 관리)

환경 변수, Settings 클래스, `.env.{APP_ENV}` 동적 로딩 테스트.

#### TestSettings (10개)

| 테스트 | 설명 |
|--------|------|
| test_default_values | 기본값이 올바르게 설정되는지 확인 |
| test_qdrant_defaults | Qdrant 관련 기본값 확인 |
| test_embedding_default | 임베딩 API URL 기본값 확인 |
| test_reranker_default | Reranker URL 기본값 확인 |
| test_langfuse_defaults | Langfuse 관련 기본값 확인 |
| test_env_override | 환경변수로 설정값 오버라이드 확인 |
| test_type_coercion | 문자열 환경변수가 올바른 타입으로 변환 확인 |
| test_case_insensitive | 환경변수 키 대소문자 무시(case_sensitive=False) 확인 |
| test_hybrid_search_defaults | HYBRID_SEARCH_ENABLED · RRF_K 기본값 확인 |
| test_hybrid_search_env_override | Hybrid Search 환경변수 오버라이드 확인 |

#### TestEnvFileDynamicLoading (2개)

| 테스트 | 설명 |
|--------|------|
| test_default_env_file_is_dev | 기본 APP_ENV에서 `.env.dev`를 로드하는지 확인 |
| test_env_file_pattern | env_file이 `.env.{APP_ENV}` 패턴인지 확인 |

#### TestGetSettings (2개)

| 테스트 | 설명 |
|--------|------|
| test_returns_settings_instance | Settings 인스턴스 반환 확인 |
| test_singleton_behavior | lru_cache 기반 싱글턴 동작 확인 |

---

### 2. test_embedding.py (임베딩 어댑터)

BGE-M3 임베딩 API 연동 테스트.

#### TestMockEmbeddingAdapter (4개)

| 테스트 | 설명 |
|--------|------|
| test_implements_interface | EmbeddingInterface 구현 확인 |
| test_returns_list_of_floats | list[float] 타입 벡터 반환 확인 |
| test_returns_1024_dimension | 1024 차원 벡터 반환 확인 |
| test_returns_consistent_dimension | 다른 입력에 동일 차원 반환 확인 |

#### TestEmbeddingAdapter (10개)

| 테스트 | 설명 |
|--------|------|
| test_implements_interface | EmbeddingInterface 구현 확인 |
| test_successful_embedding | API 응답에서 벡터 추출 반환 |
| test_sends_correct_request_body | 요청 본문에 query 필드 포함 |
| test_uses_configured_timeout | HTTP_TIMEOUT 설정 적용 확인 |
| test_timeout_raises_embedding_exception | 타임아웃 시 EmbeddingException 발생 |
| test_connect_error_raises_embedding_exception | 연결 실패 시 EmbeddingException 발생 |
| test_http_status_error_raises_embedding_exception | HTTP 에러 시 EmbeddingException 발생 |
| test_exception_has_correct_rag_code | RAG 코드 RAG100040 확인 |
| test_missing_vector_key_raises_embedding_exception | vector 키 누락 시 예외 |
| test_invalid_json_raises_embedding_exception | 유효하지 않은 JSON 시 예외 |

---

### 3. test_exceptions.py (예외 처리)

에러 코드, 커스텀 예외, 글로벌 핸들러 테스트.

#### TestExceptionClasses (8개)

| 테스트 | 설명 |
|--------|------|
| test_rag_base_exception_defaults | RAGBaseException 기본값 확인 |
| test_bad_request_exception | BadRequestException 코드 및 상태 확인 |
| test_bad_request_custom_msg | BadRequestException 커스텀 메시지 확인 |
| test_reranker_exception | RerankerException 코드 및 상태 확인 |
| test_embedding_exception | EmbeddingException 코드 및 상태 확인 |
| test_vector_store_exception | VectorStoreException 코드 및 상태 확인 |
| test_internal_server_exception | InternalServerException 코드 및 상태 확인 |
| test_inheritance | 모든 예외가 RAGBaseException 상속 확인 |

#### TestExceptionHandlers (7개)

| 테스트 | 설명 |
|--------|------|
| test_validation_error_returns_rag100020 | query 누락 시 RAG100020 응답 |
| test_empty_query_returns_rag100020 | 빈 query 시 RAG100020 응답 |
| test_negative_top_k_returns_rag100020 | 음수 top_k 시 RAG100020 응답 |
| test_http_exception_returns_standard_format | 존재하지 않는 경로 시 표준 에러 형식 |
| test_method_not_allowed_returns_standard_format | 잘못된 HTTP 메서드 시 표준 에러 형식 |
| test_error_response_no_stack_trace | 에러 응답에 스택 트레이스 미포함 확인 |
| test_normal_request_still_works | 예외 핸들러 등록 후 정상 요청 동작 확인 |

---

### 4. test_health.py (Health Check)

헬스체크 엔드포인트 테스트.

| 테스트 | 설명 |
|--------|------|
| test_health_returns_200 | /health 200 OK 응답 확인 |
| test_health_response_body | status, env 필드 포함 확인 |
| test_health_env_matches_settings | env가 Settings.APP_ENV와 일치 확인 |

---

### 5. test_main_startup.py (startup Hybrid 인덱스 검증)

`disable_hybrid_if_fulltext_index_missing` startup 훅 테스트.

#### TestDisableHybridIfFulltextIndexMissing (5개)

| 테스트 | 설명 |
|--------|------|
| test_noop_when_hybrid_disabled | HYBRID_SEARCH_ENABLED=false면 검증 없이 통과 |
| test_keeps_enabled_when_index_exists | full-text index 존재 시 플래그 유지 |
| test_disables_when_index_missing | index 없으면 플래그를 false로 비활성화 + ERROR 로그 |
| test_disables_when_check_raises | index 검증 중 예외 시 false로 비활성화 + WARNING 로그 |
| test_no_exception_leaks_on_failure | 검증 실패가 startup으로 전파되지 않음 |

---

### 6. test_monitoring.py (Langfuse 트레이싱)

Langfuse 통합 트레이싱 테스트.

#### TestGetLangfuseClient (4개)

| 테스트 | 설명 |
|--------|------|
| test_disabled_returns_none | LANGFUSE_ENABLED=false 시 None 반환 |
| test_empty_key_returns_none | PUBLIC_KEY 비어있으면 None 반환 |
| test_enabled_with_valid_key | 유효한 설정 시 Langfuse 인스턴스 반환 |
| test_creation_failure_returns_none | 클라이언트 생성 실패 시 None 반환 |

#### TestShutdownLangfuse (3개)

| 테스트 | 설명 |
|--------|------|
| test_flushes_client | shutdown 시 flush 호출 + 리셋 확인 |
| test_noop_when_disabled | 클라이언트 None 시 에러 없이 종료 |
| test_flush_error_handled | flush 실패 시에도 정상 종료 |

#### TestLangfuseMiddleware (14개)

| 테스트 | 설명 |
|--------|------|
| test_inherits_trace_id | 헤더 trace-id 승계 확인 |
| test_generates_trace_id | 헤더 없을 시 UUID 자동 생성 |
| test_without_langfuse | 클라이언트 None이어도 정상 처리 |
| test_langfuse_error_does_not_break_request | Langfuse 예외 시에도 요청 정상 처리 |
| test_response_header_has_trace_id | 응답 헤더에 trace-id 포함 |
| test_response_header_matches_request_trace_id | 요청/응답 trace-id 일치 |
| test_response_header_generated_trace_id | 자동 생성 trace-id 응답 포함 |
| test_empty_trace_id_header_generates_new | 빈 헤더 시 새로 생성 |
| test_health_endpoint_skips_trace_id_header | /health는 미들웨어를 우회하여 trace-id 헤더 처리 생략 |
| test_langfuse_span_output_recorded | span output 메타데이터 기록 |
| test_langfuse_span_stored_in_request_state | request.state에 span 객체 저장 |
| test_search_uses_middleware_trace_id | SearchService가 미들웨어 trace_id 사용 |
| test_parent_observation_id_passed_to_langfuse | X-LF-Parent-Id 전달 확인 |
| test_no_parent_id_header_still_works | Parent-Id 없이도 정상 동작 |

#### TestObserve (3개)

| 테스트 | 설명 |
|--------|------|
| test_returns_nullcontext_when_disabled | 비활성화 시 nullcontext 반환 |
| test_returns_context_manager_when_enabled | 활성화 시 observation 반환 |
| test_returns_nullcontext_on_failure | observation 생성 실패 시 nullcontext |

#### TestSafeUpdateSpan (3개)

| 테스트 | 설명 |
|--------|------|
| test_updates_span | 정상 span update 호출 확인 |
| test_skips_none_span | None span 시 에러 없이 스킵 |
| test_catches_update_exception | update 예외 시 에러 없이 흡수 |

#### TestSearchServiceSpanRecording (8개)

| 테스트 | 설명 |
|--------|------|
| test_embedding_span_created | 임베딩 단계 embedding span 기록 |
| test_vector_search_span_created | 벡터 검색 단계 retriever span 기록 |
| test_reranking_span_created | 리랭킹 단계 span 기록 |
| test_three_spans_created | 파이프라인에서 정확히 3개 child span 생성 |
| test_reranking_fallback_span_error | Fallback 시 span level=ERROR 기록 |
| test_langfuse_disabled_search_works | Langfuse 비활성화 시 검색 정상 동작 |
| test_span_creation_failure_does_not_break_search | span 생성 실패 시 검색 정상 동작 확인 |
| test_span_update_failure_does_not_break_search | span 업데이트 실패 시 검색 정상 동작 확인 |

---

### 7. test_qdrant_adapter.py (Qdrant 어댑터)

Qdrant dense 검색, full-text(BM25) 검색, index 검증, parent 청크 회수 테스트.

#### TestQdrantAdapter (20개) — dense 검색·필터·예외

| 테스트 | 설명 |
|--------|------|
| test_implements_interface | VectorStoreInterface 구현 확인 |
| test_uses_settings_for_connection | Settings.QDRANT_URL로 클라이언트 생성 |
| test_uses_settings_collection_name | Settings.QDRANT_COLLECTION 사용 |
| test_dept_filter_not_applied | 부서(auth_dept_id) 필터 미적용 — 전 부서 검색 개방 |
| test_excluded_docs_filter | excluded_docs가 must_not(doc_content_id) 조건으로 적용 |
| test_query_filter_includes_is_active | is_active="Y" must 조건 포함 |
| test_empty_excluded_docs_no_must_not | 빈 excluded_docs면 must_not 없음 |
| test_successful_search | content, metadata, score 포함 결과 반환 |
| test_empty_results_returns_empty_list | 결과 없으면 빈 리스트 반환 |
| test_content_field_extraction | content_field → content, 나머지 → metadata 추출 |
| test_custom_content_field | QDRANT_CONTENT_FIELD로 다른 필드명 사용 |
| test_missing_content_field_returns_empty_string | 필드 없으면 빈 문자열 반환 |
| test_unexpected_response_raises_vector_store_exception | UnexpectedResponse 시 예외 |
| test_connect_error_raises_vector_store_exception | 연결 실패 시 예외 |
| test_timeout_raises_vector_store_exception | 타임아웃 시 예외 |
| test_exception_has_correct_rag_code | RAG100060 코드 확인 |
| test_parse_error_raises_vector_store_exception | 파싱 실패 시 예외 |
| test_connect_error_logs_message | 연결 실패 에러 로그 기록 |
| test_timeout_logs_message | 타임아웃 에러 로그 기록 |
| test_search_returns_point_id | 반환 dict에 _point_id(Qdrant point.id) 포함 |

#### TestQdrantAdapterTextSearch (7개) — full-text(BM25) 검색

| 테스트 | 설명 |
|--------|------|
| test_uses_match_text_filter | text_for_search 필드에 MatchText 조건 사용 |
| test_reuses_common_filter | is_active / excluded_docs 공통 필터 재사용 |
| test_returns_point_id_and_content | content + _point_id 반환 |
| test_empty_results | 결과 없으면 빈 리스트 반환 |
| test_connect_error_raises | 연결 실패 시 VectorStoreException |
| test_timeout_raises | 타임아웃 시 예외 |
| test_unexpected_response_raises | UnexpectedResponse 시 예외 |

#### TestQdrantAdapterCheckFulltextIndex (6개) — index 검증

| 테스트 | 설명 |
|--------|------|
| test_returns_true_when_text_index_exists | text 타입 payload index 존재 시 True |
| test_returns_false_when_field_missing | 해당 필드 index 없으면 False |
| test_returns_false_when_not_text_type | text 타입이 아니면 False |
| test_returns_false_on_connect_error | 연결 실패 시 False |
| test_returns_false_on_timeout | 타임아웃 시 False |
| test_returns_false_on_unexpected_response | UnexpectedResponse 시 False |

#### TestFetchChunksByParents (4개) — parent 청크 회수

| 테스트 | 설명 |
|--------|------|
| test_empty_input_skips_scroll | 빈 입력이면 scroll 미호출 + 빈 리스트 |
| test_filter_has_doc_parent_active | doc_content_id · parent_id · is_active 필터 구성 확인 |
| test_pagination_aggregates_all_pages | scroll 페이지네이션으로 전건 수집 |
| test_scroll_per_document | 문서별 병렬 scroll 수행 |

---

### 8. test_reranker_adapter.py (리랭커 어댑터)

bge-reranker-v2-m3 리랭커 어댑터 테스트.

#### TestRerankerAdapter (19개)

| 테스트 | 설명 |
|--------|------|
| test_implements_interface | RerankerInterface 구현 확인 |
| test_rerank_success | API 응답에서 리랭킹 결과 추출 반환 |
| test_rerank_success_list_format | 리스트 직접 반환 형식 처리 |
| test_rerank_result_structure | index, score, text 포함 확인 |
| test_rerank_top_k_slicing | top_k 결과 수 제한 |
| test_sends_correct_request_body | query, texts, return_text 포함 전송 |
| test_uses_configured_timeout | HTTP_TIMEOUT 설정 적용 |
| test_empty_texts_returns_empty_list | 빈 텍스트 시 API 미호출 + 빈 리스트 |
| test_empty_texts_logs_warning | 빈 텍스트 시 warning 로그 |
| test_timeout_raises_reranker_exception | 타임아웃 시 RerankerException |
| test_connect_error_raises_reranker_exception | 연결 실패 시 예외 |
| test_http_error_raises_reranker_exception | HTTP 에러 시 예외 |
| test_missing_value_key_raises_reranker_exception | value 키 누락 시 예외 |
| test_malformed_item_raises_reranker_exception | 아이템 키 누락 시 예외 |
| test_non_list_value_raises_reranker_exception | value가 배열 아닐 때 예외 |
| test_invalid_response_raises_reranker_exception | 유효하지 않은 JSON 시 예외 |
| test_exception_has_correct_rag_code | RAG100050 코드 확인 |
| test_timeout_logs_error | 타임아웃 에러 로그 기록 |
| test_connect_error_logs_error | 연결 실패 에러 로그 기록 |

---

### 9. test_responses.py (표준 응답 규격)

RAGCode, APIResponse, 응답 헬퍼 함수 테스트.

#### TestRAGCode (4개)

| 테스트 | 설명 |
|--------|------|
| test_code_format_9_chars | 모든 코드 9자리(RAG + 6자리) 확인 |
| test_defined_codes | 정의된 코드 존재 확인 |
| test_default_messages | 각 코드 기본 메시지 존재 확인 |
| test_specific_default_messages | PRD 정의 기본 메시지 확인 |

#### TestAPIResponse (3개)

| 테스트 | 설명 |
|--------|------|
| test_with_data | data 포함 시 to_dict에 포함 |
| test_without_data_excludes_none | data=None 시 필드 생략 |
| test_explicit_none_excludes | 명시적 None도 필드 생략 |

#### TestSuccessResponse (4개)

| 테스트 | 설명 |
|--------|------|
| test_default_code_and_msg | 기본 SEARCH_SUCCESS 코드 + 메시지 |
| test_custom_msg | 커스텀 메시지 오버라이드 |
| test_custom_code | 다른 코드 지정 |
| test_includes_data | data 항상 포함 |

#### TestErrorResponse (4개)

| 테스트 | 설명 |
|--------|------|
| test_default_msg | 기본 메시지 사용 |
| test_custom_msg | 커스텀 메시지 오버라이드 |
| test_no_data_field | 에러 응답에 data 필드 없음 |
| test_reranker_failure | 리랭커 실패 코드 확인 |

#### TestNoResultResponse (2개)

| 테스트 | 설명 |
|--------|------|
| test_code_and_msg | 코드와 메시지 확인 |
| test_no_data_field | data 필드 없음 확인 |

---

### 10. test_search.py (검색 서비스 + 엔드포인트)

핵심 검색 파이프라인(임베딩 → dense/Hybrid → RRF → 리랭킹 → parent 확장) 및 API 엔드포인트 테스트.

#### TestInterfaces (2개)

| 테스트 | 설명 |
|--------|------|
| test_mock_vector_store_implements_interface | MockVectorStore 인터페이스 구현 확인 |
| test_mock_reranker_implements_interface | MockReranker 인터페이스 구현 확인 |

#### TestMockVectorStore (2개)

| 테스트 | 설명 |
|--------|------|
| test_returns_correct_count | top_k 만큼 결과 반환 |
| test_result_structure | content, metadata, score 포함 |

#### TestMockReranker (3개)

| 테스트 | 설명 |
|--------|------|
| test_returns_limited_by_top_k | top_k 결과 수 제한 |
| test_result_structure | index, score, text 포함 |
| test_sorted_by_score | score 내림차순 정렬 |

#### TestSearchService (12개)

| 테스트 | 설명 |
|--------|------|
| test_search_returns_expected_structure | query, trace_id, results 포함 |
| test_result_item_structure | rank, score, content, metadata 포함 |
| test_top_k_limits_results | top_k 결과 수 제한 |
| test_rank_starts_at_1 | rank 1부터 시작 |
| test_empty_results_skips_reranker | 빈 결과 시 리랭커 스킵 |
| test_embed_called_with_query | embed() 쿼리 문자열 호출 |
| test_embed_vector_passed_to_vector_store | 벡터가 vector_store.search()에 전달 |
| test_embedding_exception_propagates | EmbeddingException 전파 |
| test_response_metadata_contains_only_allowed_fields | RESPONSE_METADATA_FIELDS만 포함 |
| test_score_threshold_filters_low_scores | 임계값 미만 결과 제외 |
| test_score_threshold_zero_returns_all | 임계값 0.0 시 전체 반환 |
| test_score_threshold_adjusts_rank | 필터링 후 rank 재정렬 |

#### TestRRFFuse (9개) — Reciprocal Rank Fusion 합산

| 테스트 | 설명 |
|--------|------|
| test_both_empty_returns_empty | 양쪽 빈 입력이면 빈 리스트 |
| test_dense_only_preserves_order | dense만 있으면 순서 보존 |
| test_bm25_only_preserves_order | bm25만 있으면 순서 보존 |
| test_bm25_only_preserves_bm25_score | bm25-only 시 원본 bm25 score 보존 |
| test_overlap_sums_and_marks_source | 양쪽 매칭 시 RRF 합산 + _source=dense+bm25 |
| test_overlap_preserves_dense_score | 겹칠 때 원본 score는 dense 값 유지 |
| test_sorted_by_rrf_score_desc | _rrf_score 내림차순 정렬 |
| test_rrf_k_parameter | RRF k 파라미터 반영 |
| test_missing_point_id_skipped | _point_id 없는 항목 스킵 |

#### TestHybridSearchPipeline (12개) — Dense + BM25 + 실패 매트릭스 + span

| 테스트 | 설명 |
|--------|------|
| test_hybrid_disabled_calls_dense_only | 플래그 off 시 dense-only 경로 |
| test_hybrid_enabled_calls_both | 플래그 on 시 dense + bm25 둘 다 호출 |
| test_hybrid_bm25_failure_falls_back_to_dense | bm25 실패 시 dense만으로 진행 + WARN |
| test_hybrid_dense_failure_falls_back_to_bm25 | dense 실패 시 bm25만으로 진행 + WARN |
| test_hybrid_both_failures_raise | 양쪽 실패 시 VectorStoreException |
| test_hybrid_response_strips_internal_fields | 응답에서 _rrf_score 등 내부 필드 제거 |
| test_hybrid_reranker_fallback_uses_original_score | hybrid + 리랭커 fallback 시 원본 score 노출 |
| test_hybrid_span_input_includes_search_mode | vector-search span input에 search_mode 포함 |
| test_hybrid_creates_child_spans | hybrid 시 dense-search/bm25-search/rrf-fusion child span 생성 |
| test_dense_only_mode_has_no_child_spans | dense-only 시 child span 없음 |
| test_rrf_fusion_span_input_has_counts | rrf-fusion span에 dense/bm25 count 기록 |
| test_runtime_settings_mutation_propagates_to_service | 런타임 settings 변경이 서비스에 즉시 반영 |

#### TestParentExpansion (7개) — parent ±1 인접 청크 확장

| 테스트 | 설명 |
|--------|------|
| test_flag_off_no_expansion | PARENT_EXPANSION_ENABLED=false 시 청크 결과 그대로 |
| test_expansion_merges_parent_chunks | parent N-1·N·N+1 청크를 chunk_index 순으로 병합 |
| test_defensive_passthrough_for_missing_parent_id | parent_id 없으면 단일 result로 통과 |
| test_mixed_expand_and_passthrough | 확장 청크와 통과 청크 혼합 처리 |
| test_dedup_overlapping_parents | 겹치는 parent를 _point_id로 dedup |
| test_expansion_error_falls_back_to_chunks | 확장 단계 오류 시 청크 결과로 폴백 |
| test_malformed_parent_id_passthrough | parent_id 형변환 불가 시 통과(방어) |

#### TestSearchEndpoint (11개)

| 테스트 | 설명 |
|--------|------|
| test_search_success | 정상 검색 RAG100000 반환 |
| test_search_response_data_structure | data에 query, trace_id, results 포함 |
| test_search_with_custom_top_k | 커스텀 top_k 지정 |
| test_search_default_params_from_settings | 미지정 시 기본값 Settings 적용 |
| test_search_result_item_fields | 결과 아이템 필드 확인 |
| test_missing_query_returns_400 | query 누락 시 400 |
| test_missing_user_depts_returns_400 | user_depts 누락 시 400 |
| test_empty_user_depts_returns_400 | 빈 user_depts 시 400(RAG100020) |
| test_string_user_depts_returns_validation_error | user_depts 타입 오류 시 검증 에러 |
| test_search_with_excluded_docs | excluded_docs 전달 시 정상 동작 |
| test_search_without_excluded_docs | excluded_docs 생략 시 기본값 `[]` 동작 |

#### TestDIBinding (1개)

| 테스트 | 설명 |
|--------|------|
| test_always_uses_real_adapters | APP_ENV에 관계없이 실제 어댑터(EmbeddingAdapter/QdrantAdapter/RerankerAdapter) 주입 확인 |

#### TestRerankerPipelineIntegration (8개)

| 테스트 | 설명 |
|--------|------|
| test_pipeline_with_reranker_adapter | RerankerAdapter 전체 파이프라인 동작 |
| test_pipeline_result_has_metadata | 리랭커 결과의 원본 metadata 매핑 |
| test_fallback_returns_results_on_reranker_failure | 리랭커 장애 시 Fallback 결과 반환 |
| test_endpoint_fallback_on_reranker_error | 엔드포인트 Fallback HTTP 200 응답 |
| test_fallback_applies_top_k | Fallback 결과 top_k 슬라이싱 |
| test_fallback_has_correct_metadata | Fallback metadata 필터링 |
| test_fallback_logs_warning | Fallback 시 WARNING 로그 |
| test_normal_search_no_fallback_flag | 정상 시 fallback 키 없음 |

---

## 통합 테스트 상세

### test_search_integration.py (통합 테스트)

실제 임베딩 API + Qdrant 서버 연동 E2E 테스트.

**실행 조건**: `pytest --run-integration`
**필요 서비스**: Embedding API (`EMBEDDING_API_URL`), Qdrant (`QDRANT_URL`)

#### TestSearchPipelineIntegration (3개)

| 테스트 | 설명 |
|--------|------|
| test_full_pipeline_returns_success | 정상 쿼리 RAG100000 응답 확인 |
| test_pipeline_response_structure | data에 query, trace_id, results 포함 |
| test_pipeline_with_custom_top_k | top_k 결과 수 제한 확인 |
