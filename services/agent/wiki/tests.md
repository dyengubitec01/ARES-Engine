# 테스트 문서

## 개요

Agent Server의 테스트 문서입니다.

- **테스트 프레임워크**: pytest, pytest-asyncio
- **총 테스트 수**: 408개 (단위) + 33개 (통합, 별도 실행) = **441개**
- **Python 버전**: 3.11+

## 실행 방법

### 단위 테스트

```bash
# 전체 단위 테스트 실행 (통합 테스트 자동 제외)
uv run pytest

# 상세 출력
uv run pytest -v

# 특정 파일 실행
uv run pytest tests/test_chat.py -v

# 특정 클래스 실행
uv run pytest tests/test_chat.py::TestChatRequestSchema -v

# 특정 테스트 함수 실행
uv run pytest tests/test_chat.py::TestFormatSSE::test_format_sse_thought -v

# 커버리지 포함 실행
uv run pytest --cov=app --cov-report=term-missing

# HTML 커버리지 리포트 생성
uv run pytest --cov=app --cov-report=html
# → htmlcov/index.html 에서 확인
```

### 통합 테스트

통합 테스트는 실제 LLM 서버, LangFuse 서버, RAG/Tool 서버가 필요합니다.
서버가 없으면 자동으로 스킵됩니다.

```bash
# 통합 테스트 실행
uv run pytest tests/integration/ -m integration -v

# tox로 실행
tox -e integration
```

### tox

```bash
tox              # 단위 테스트
tox -e integration  # 통합 테스트
tox -e coverage  # 커버리지 리포트
tox -e lint      # 린트 검사
```

---

## 단위 테스트 파일 목록

| 파일 | 테스트 수 | 대상 모듈 |
|------|----------|----------|
| test_chat.py | 40 | Chat API, SSE 포맷, 토큰 usage, 검색 고지 |
| test_config.py | 26 | 설정 관리, APP_ENV 로딩 |
| test_exception_handling.py | 34 | 예외 처리, 에러 코드 |
| test_health_models.py | 14 | Health/Models API |
| test_llm_factory.py | 33 | LLM 팩토리, Failover, chain 호출 |
| test_logging_config.py | 5 | structlog 설정 (ADR-004) |
| test_middleware.py | 5 | request_id + Access Log 미들웨어 |
| test_nodes_prompt_generation_link.py | 2 | LangFuse Prompt-Generation 연결 |
| test_prompt_manager.py | 21 | LangFuse 프롬프트 관리, fallback 체인 |
| test_query_rewriter.py | 32 | Query Rewriter 노드 |
| test_rag_client.py | 24 | RAG 클라이언트, 검색 요청 body |
| test_retriever_synthesizer.py | 27 | Retriever/Synthesizer 노드 |
| test_router.py | 44 | Router 노드 (의도 분류, SKIP 플래그) |
| test_tool_client.py | 30 | Tool 클라이언트 |
| test_tool_executor.py | 14 | Tool Executor 노드 |
| test_tracing.py | 29 | LangFuse 트레이싱, trace context 추출 |
| test_workflow_graph.py | 28 | 워크플로우 그래프 |
| **합계** | **408** | |

---

## 통합 테스트 파일 목록

| 파일 | 테스트 수 | 대상 | 필요 서버 |
|------|----------|------|----------|
| test_chat_integration.py | 10 | Chat API E2E | LLM |
| test_langfuse_integration.py | 9 | LangFuse 트레이싱 + Cross-service 헤더 | LLM, LangFuse |
| test_prompt_management.py | 9 | 프롬프트 fetch + fallback 체인 | LangFuse |
| test_workflow_routes.py | 5 | 워크플로우 라우트별 실행 (rag/tool/both) | LLM, RAG, Tool |
| **합계** | **33** | | |

### 통합 테스트 사전 조건

`tests/integration/conftest.py`에 정의된 skip 조건:

| 조건 | 환경 | 스킵 기준 |
|------|------|----------|
| `skip_no_llm` | LLM 서버 | `PRIMARY_LLM_BASE_URL` 연결 불가 시 스킵 |
| `skip_no_langfuse` | LangFuse | `LANGFUSE_TRACING_ENABLED=false`이거나 키 미설정 시 스킵 |
| `skip_no_rag` | RAG 서버 | `RAG_BASE_URL` 연결 불가 시 스킵 |
| `skip_no_tool` | Tool 서버 | `TOOL_BASE_URL` 연결 불가 시 스킵 |

---

## 테스트 상세

### 1. test_chat.py (Chat API) — 40개

SSE 스트리밍 엔드포인트, 요청 스키마, 토큰 usage 집계, 검색 실패 고지 테스트.

#### TestFormatSSE (8개)
| 테스트 | 설명 |
|--------|------|
| test_format_sse_thought | thought 이벤트 포맷 검증 |
| test_format_sse_message | message 이벤트 포맷 검증 |
| test_format_sse_error | error 이벤트 포맷 검증 |
| test_format_sse_done | done 이벤트 포맷 검증 (enum 코드) |
| test_format_sse_done_with_sources | done 이벤트 sources 포함 확인 |
| test_format_sse_done_error_with_empty_sources | 에러 시 빈 sources 배열 확인 |
| test_format_sse_korean | 한글 데이터 처리 확인 |
| test_format_sse_done_with_usage | done 이벤트 usage 필드 포함 확인 |

#### TestChatRequestSchema (7개)
| 테스트 | 설명 |
|--------|------|
| test_valid_request_minimal | 최소 필수 필드로 생성 |
| test_valid_request_full | 모든 필드로 생성 |
| test_missing_query | query 누락 시 ValidationError |
| test_missing_session_id | session_id 누락 시 ValidationError |
| test_empty_history | 빈 history 허용 |
| test_blank_query_rejected | 공백 query 거부 |
| test_blank_session_id_rejected | 공백 session_id 거부 |

#### TestChatRequestUserDeptArray (7개)
| 테스트 | 설명 |
|--------|------|
| test_user_depts_array_accepted | user_depts 배열 수용 |
| test_user_depts_single_item_array | 단일 항목 배열 수용 |
| test_user_depts_empty_list_rejected | 빈 배열 거부 |
| test_user_depts_null_rejected | null 거부 |
| test_user_depts_missing_rejected | 필드 누락 거부 |
| test_user_depts_blank_item_rejected | 빈 문자열 항목 거부 |
| test_user_depts_whitespace_item_rejected | 공백 항목 거부 |

#### TestChatRequestExcludedDocs (3개)
| 테스트 | 설명 |
|--------|------|
| test_excluded_docs_accepted | excluded_docs 배열 수용 |
| test_excluded_docs_default_empty | 미지정 시 빈 배열 기본값 |
| test_excluded_docs_empty_list_accepted | 빈 배열 허용 |

#### TestErrorEventGeneration (2개)
| 테스트 | 설명 |
|--------|------|
| test_business_exception_format | BusinessException 에러 이벤트 변환 |
| test_generic_error_format | 일반 에러 AGT5000 변환 |

#### TestSSEEventSequence (1개)
| 테스트 | 설명 |
|--------|------|
| test_event_format_consistency | 모든 이벤트 타입 일관된 포맷 확인 |

#### TestStreamWorkflowUsage (4개)
| 테스트 | 설명 |
|--------|------|
| test_multi_on_chat_model_end_summation | 여러 LLM 호출의 토큰 usage 합산 |
| test_usage_metadata_missing_zero_and_warn | usage_metadata 누락 시 0 처리 + WARN 로그 |
| test_business_exception_partial_usage | 에러 시 부분 누적 usage 전달 |
| test_stream_completed_log_fields | stream_completed 로그 필드 검증 |

#### TestStreamWorkflowNoticeAndResponse (8개)
| 테스트 | 설명 |
|--------|------|
| test_notice_sent_on_rag_empty | 검색 0건 시 고지 문구 선전송 |
| test_notice_sent_on_rag_error | 검색 오류 시 고지 문구 선전송 |
| test_no_notice_on_rag_ok | 검색 성공 시 고지 미전송 |
| test_no_notice_on_non_rag_route | rag 외 경로에서는 고지 미전송 |
| test_done_response_uses_postprocessed_value | done.response에 후처리 정본 사용 |
| test_error_done_partial_response | 에러 done에 부분 응답 포함 |
| test_done_response_default_empty | 기본 done.response 빈 문자열 |
| test_stream_gate_filters_non_synthesizer_chunks | synthesizer 외 노드의 LLM 청크 차단 |

---

### 2. test_config.py (설정 관리) — 26개

환경 변수, APP_ENV 기반 env 파일 로딩, 모델 설정 테스트.

#### TestSettings (12개)
| 테스트 | 설명 |
|--------|------|
| test_default_values | 기본값 확인 |
| test_langfuse_disabled_by_default | LangFuse 기본 비활성화 |
| test_langfuse_enabled_with_keys | 키 있을 때 LangFuse 활성화 |
| test_llm_max_tokens_default | LLM_MAX_TOKENS 기본값 |
| test_llm_temperature_default | LLM_TEMPERATURE 기본값 |
| test_llm_max_tokens_override | LLM_MAX_TOKENS 오버라이드 |
| test_llm_temperature_override | LLM_TEMPERATURE 오버라이드 |
| test_include_thoughts_default_false | INCLUDE_THOUGHTS 기본 false |
| test_include_thoughts_can_be_enabled | INCLUDE_THOUGHTS 활성화 가능 |
| test_app_env_default | APP_ENV 기본값 dev |
| test_app_env_override | APP_ENV 오버라이드 |
| test_env_file_dynamic_loading | APP_ENV에 따른 `.env.{APP_ENV}` 동적 로딩 |

#### TestModelConfig (5개)
| 테스트 | 설명 |
|--------|------|
| test_get_role | 역할 설정 조회 |
| test_get_role_not_found | 없는 역할 조회 시 None |
| test_get_model_for_role | 역할별 모델명 조회 |
| test_get_fallback_role | fallback 역할 조회 |
| test_get_fallback_role_none | fallback 없는 경우 |

#### TestLoadModelConfig (7개)
| 테스트 | 설명 |
|--------|------|
| test_load_valid_config | 유효한 설정 파일 로드 |
| test_load_missing_file | 파일 없을 때 에러 |
| test_load_missing_roles | roles 섹션 누락 에러 |
| test_load_missing_servers | servers 섹션 누락 에러 |
| test_load_empty_file | 빈 파일 에러 |
| test_load_malformed_yaml | 잘못된 YAML 형식 에러 |
| test_load_invalid_schema | 스키마 불일치 에러 |

#### TestSingleton (2개)
| 테스트 | 설명 |
|--------|------|
| test_get_settings_singleton | Settings 싱글톤 확인 |
| test_get_model_config_singleton | ModelConfig 싱글톤 확인 |

---

### 3. test_exception_handling.py (예외 처리) — 34개

에러 코드, 비즈니스 예외, 응답 포맷 테스트.

#### TestErrorCode (10개)
| 테스트 | 설명 |
|--------|------|
| test_error_code_success_properties | SUCCESS 코드 속성 |
| test_error_code_validation_error_properties | VALIDATION_ERROR 속성 |
| test_error_code_invalid_request_properties | INVALID_REQUEST 속성 |
| test_error_code_internal_error_properties | INTERNAL_ERROR 속성 |
| test_error_code_llm_connection_properties | LLM_CONNECTION 속성 |
| test_error_code_llm_response_properties | LLM_RESPONSE 속성 |
| test_error_code_rag_search_properties | RAG_SEARCH 속성 |
| test_error_code_tool_execution_properties | TOOL_EXECUTION 속성 |
| test_error_code_all_servers_down_properties | ALL_SERVERS_DOWN 속성 |
| test_all_error_codes_have_properties | 모든 에러 코드 속성 확인 |

#### TestBusinessException (4개)
| 테스트 | 설명 |
|--------|------|
| test_basic_exception | 기본 예외 생성 |
| test_exception_with_detail | detail 포함 예외 |
| test_exception_inherits_from_exception | Exception 상속 확인 |
| test_exception_can_be_raised_and_caught | raise/catch 동작 확인 |

#### TestCommonResponse (7개)
| 테스트 | 설명 |
|--------|------|
| test_success_response_default | 기본 성공 응답 |
| test_success_response_with_data | data 포함 성공 응답 |
| test_success_response_custom_error_code | 커스텀 에러 코드 |
| test_error_response_basic | 기본 에러 응답 |
| test_error_response_with_detail | detail 포함 에러 응답 |
| test_response_serialization | JSON 직렬화 |
| test_error_response_serialization | 에러 응답 직렬화 |

#### TestExceptionHandlers (5개)
| 테스트 | 설명 |
|--------|------|
| test_business_exception_handler_validation_error | VALIDATION_ERROR 핸들러 |
| test_business_exception_handler_llm_error | LLM_CONNECTION 핸들러 |
| test_unhandled_exception_handler | 미처리 예외 핸들러 |
| test_request_validation_error_handler | RequestValidationError 핸들러 |
| test_request_validation_error_type_mismatch | 타입 불일치 에러 |

#### TestExceptionHandlerHttpStatus (8개)
| 테스트 | 설명 |
|--------|------|
| test_http_status_400_validation | VALIDATION_ERROR → 400 |
| test_http_status_400_invalid_request | INVALID_REQUEST → 400 |
| test_http_status_500_internal | INTERNAL_ERROR → 500 |
| test_http_status_503_llm_connection | LLM_CONNECTION → 503 |
| test_http_status_502_llm_response | LLM_RESPONSE → 502 |
| test_http_status_503_rag_search | RAG_SEARCH → 503 |
| test_http_status_503_tool_execution | TOOL_EXECUTION → 503 |
| test_http_status_503_all_servers_down | ALL_SERVERS_DOWN → 503 |

---

### 4. test_health_models.py (Health/Models API) — 14개

헬스체크 및 모델 정보 API 테스트.

#### TestHealthEndpoint (5개)
| 테스트 | 설명 |
|--------|------|
| test_health_returns_200 | /health 200 응답 |
| test_health_response_format | 응답 포맷 확인 |
| test_health_data_contains_status | status 필드 포함 |
| test_health_data_contains_version | version 필드 포함 |
| test_health_data_contains_timestamp | timestamp 필드 포함 |

#### TestDeepHealthEndpoint (4개)
| 테스트 | 설명 |
|--------|------|
| test_deep_health_returns_200 | `/health?deep=true` 200 응답 |
| test_deep_health_contains_llm_servers | llm_servers 필드 포함 |
| test_deep_health_server_status_format | 서버 상태 포맷 확인 |
| test_deep_health_disconnected_server | 연결 끊긴 서버 처리 |

#### TestModelsEndpoint (5개)
| 테스트 | 설명 |
|--------|------|
| test_models_returns_200 | /v1/models 200 응답 |
| test_models_response_format | 응답 포맷 확인 |
| test_models_contains_roles_list | roles 리스트 포함 |
| test_models_role_format | 역할 포맷 확인 |
| test_models_contains_primary_role | primary 역할 포함 |

---

### 5. test_llm_factory.py (LLM 팩토리) — 33개

LLM 인스턴스 생성, Failover, chain 호출 테스트.

#### TestLLMFactory (8개)
| 테스트 | 설명 |
|--------|------|
| test_get_model_for_role | 역할별 모델 조회 |
| test_get_model_for_unknown_role | 알 수 없는 역할 처리 |
| test_get_fallback_role | fallback 역할 조회 |
| test_fallback_message | fallback 메시지 |
| test_get_base_url | base URL 조회 |
| test_get_model_with_fallback_direct | 직접 모델 조회 |
| test_get_model_with_fallback_chain | fallback 체인 조회 |
| test_get_model_with_fallback_unknown | 알 수 없는 역할 fallback |

#### TestLLMFactoryLangChain (8개)
| 테스트 | 설명 |
|--------|------|
| test_get_llm_returns_chat_openai | ChatOpenAI 인스턴스 반환 |
| test_get_llm_includes_max_tokens | max_tokens 설정 반영 |
| test_get_llm_includes_temperature | temperature 설정 반영 |
| test_get_llm_caching_same_role | 동일 역할 캐싱 |
| test_get_llm_different_roles_different_instances | 다른 역할 다른 인스턴스 |
| test_get_llm_unknown_role_raises_error | 알 수 없는 역할 에러 |
| test_get_llm_api_key_not_needed | API 키 불필요 |
| test_get_available_roles | 사용 가능 역할 목록 |

#### TestLLMFactoryAsync (3개)
| 테스트 | 설명 |
|--------|------|
| test_invoke_returns_ai_message | invoke AI 메시지 반환 |
| test_stream_yields_chunks | stream 청크 반환 |
| test_invoke_unknown_role_raises_error | invoke 시 알 수 없는 역할 에러 |

#### TestLLMFactoryFailover (10개)
| 테스트 | 설명 |
|--------|------|
| test_invoke_with_failover_success | failover 없이 정상 호출 |
| test_invoke_with_failover_on_connect_error | 연결 에러 시 failover |
| test_invoke_with_failover_on_timeout | 타임아웃 시 failover |
| test_invoke_with_failover_graceful_degradation | 전체 실패 시 graceful degradation |
| test_invoke_with_failover_retry_before_failover | failover 전 재시도 확인 |
| test_invoke_with_failover_logging | failover 로그 기록 |
| test_stream_with_failover_success | 스트림 정상 호출 |
| test_stream_with_failover_on_error | 스트림 에러 시 failover |
| test_stream_with_failover_graceful_degradation | 스트림 전체 실패 처리 |
| test_invoke_with_failover_unknown_role | 알 수 없는 역할 전파 |

#### TestLLMFactoryChainFailover (4개)
| 테스트 | 설명 |
|--------|------|
| test_chain_invoke_success | `prompt \| llm` chain 정상 호출 |
| test_chain_failover_on_connect_error | chain 연결 에러 시 failover |
| test_chain_graceful_degradation | chain 전체 실패 처리 |
| test_chain_passes_trace_metadata_to_tracing_config | trace_metadata 전달 확인 |

---

### 6. test_logging_config.py (로깅 설정) — 5개

structlog 설정 테스트 (ADR-004).

#### TestConfigureLogging (5개)
| 테스트 | 설명 |
|--------|------|
| test_console_renderer_in_dev_mode | 개발 모드 컬러 텍스트 렌더러 |
| test_json_renderer_in_prod_mode | 운영 모드 JSON 렌더러 |
| test_json_format_output | JSON 출력 포맷 확인 |
| test_noisy_loggers_suppressed | 노이즈 로거 억제 |
| test_file_handler_rotation_config | 파일 핸들러 로테이션 설정 |

---

### 7. test_middleware.py (미들웨어) — 5개

request_id 생성 및 Access Log 미들웨어 테스트.

#### TestLoggingMiddleware (5개)
| 테스트 | 설명 |
|--------|------|
| test_request_id_generated | request_id 생성 확인 |
| test_unique_request_ids | 요청마다 고유 request_id |
| test_access_log_emitted | Access Log 기록 확인 |
| test_access_log_contains_fields | Access Log 필드 확인 |
| test_access_log_on_exception | 예외 발생 시 Access Log 기록 |

---

### 8. test_nodes_prompt_generation_link.py (Prompt-Generation 연결) — 2개

LangFuse Prompt-Generation 연결을 위한 metadata 보존 테스트.

#### TestPartialPreservesMetadata (2개)
| 테스트 | 설명 |
|--------|------|
| test_partial_preserves_langfuse_prompt_metadata | `partial()` 후 langfuse_prompt metadata 보존 |
| test_partial_without_metadata_returns_none | metadata 없을 때 None 반환 |

---

### 9. test_prompt_manager.py (프롬프트 관리) — 21개

LangFuse 프롬프트 fetch 및 3단계 fallback 체인 테스트.

#### TestPromptConfig (5개)
| 테스트 | 설명 |
|--------|------|
| test_load_config | prompts.yaml 로드 |
| test_get_variables | 프롬프트 기대 변수 조회 |
| test_get_type | 프롬프트 타입(chat/text) 조회 |
| test_unknown_prompt_raises | 미등록 프롬프트 조회 시 KeyError |
| test_missing_file_raises | 설정 파일 없을 때 FileNotFoundError |

#### TestPromptManagerFallbackChain (4개)
| 테스트 | 설명 |
|--------|------|
| test_fallback_to_hardcoded_when_disabled | 비활성 시 하드코딩 프롬프트 사용 |
| test_fallback_to_json_when_langfuse_fails | LangFuse 실패 시 fallback JSON 사용 |
| test_fallback_to_hardcoded_when_json_missing | JSON 없으면 하드코딩으로 |
| test_no_fallback_raises_runtime_error | fallback 전무 시 RuntimeError |

#### TestPromptManagerLangFuse (2개)
| 테스트 | 설명 |
|--------|------|
| test_fetch_from_langfuse | LangFuse에서 프롬프트 fetch |
| test_label_always_production | 라벨은 항상 production |

#### TestPromptManagerDisabled (1개)
| 테스트 | 설명 |
|--------|------|
| test_disabled_skips_langfuse_call | 비활성 시 LangFuse API 미호출 |

#### TestPromptManagerValidation (2개)
| 테스트 | 설명 |
|--------|------|
| test_validate_matching_variables | 변수 일치 시 통과 |
| test_validate_mismatched_variables_raises | 변수 불일치 시 ValueError |

#### TestPromptManagerPrefetch (3개)
| 테스트 | 설명 |
|--------|------|
| test_prefetch_all_calls_langfuse | 전체 프롬프트 pre-fetch |
| test_prefetch_skipped_when_disabled | 비활성 시 pre-fetch 스킵 |
| test_prefetch_continues_on_failure | 일부 실패해도 계속 진행 |

#### TestSettingsPromptConfig (4개)
| 테스트 | 설명 |
|--------|------|
| test_default_prompt_settings | 프롬프트 설정 기본값 |
| test_prompt_enabled_requires_langfuse | LangFuse 비활성 시 프롬프트도 비활성 |
| test_prompt_enabled_with_keys | 키 설정 시 활성화 |
| test_prompt_disabled_explicitly | 명시적 비활성화 |

---

### 10. test_query_rewriter.py (Query Rewriter) — 32개

질문 재구성 노드 테스트.

#### TestRewriterPrompt (3개)
| 테스트 | 설명 |
|--------|------|
| test_prompt_is_chat_prompt_template | ChatPromptTemplate 타입 |
| test_prompt_has_required_variables | 필수 변수 포함 |
| test_prompt_format_produces_messages | 메시지 생성 확인 |

#### TestHistoryFormatting (6개)
| 테스트 | 설명 |
|--------|------|
| test_format_empty_history | 빈 이력 포맷 |
| test_format_single_turn_history | 단일 턴 포맷 |
| test_format_multi_turn_history | 다중 턴 포맷 |
| test_format_assistant_role_as_xml_tag | assistant 역할 XML 태그 변환 |
| test_ai_prefix_not_accumulated_across_turns | 턴 간 "AI: " 접두사 누적 방지 |
| test_no_ai_prefix_pattern_in_format | 포맷 결과에 "AI: " 패턴 부재 |

#### TestRewriterNodeNoHistory (3개)
| 테스트 | 설명 |
|--------|------|
| test_no_history_returns_original_query | 이력 없으면 원본 반환 |
| test_no_history_no_llm_call | 이력 없으면 LLM 미호출 |
| test_no_history_thought_message | 이력 없을 때 thought 메시지 |

#### TestRewriterNodeWithHistory (5개)
| 테스트 | 설명 |
|--------|------|
| test_with_history_calls_llm | 이력 있으면 LLM 호출 |
| test_llm_called_with_primary_role | rewriter가 `primary` role로 호출되는지 확인 |
| test_llm_called_with_session_id | session_id 전달 확인 |
| test_llm_called_with_request_type | request_type 전달 확인 |
| test_with_history_thought_message | 이력 있을 때 thought 메시지 |

#### TestOutputParsing (4개)
| 테스트 | 설명 |
|--------|------|
| test_empty_response_fallback_to_original | 빈 응답 시 원본 fallback |
| test_whitespace_response_fallback_to_original | 공백 응답 시 원본 fallback |
| test_none_content_fallback_to_original | None 응답 시 원본 fallback |
| test_response_stripped | 응답 strip 처리 |

#### TestFailoverBehavior (1개)
| 테스트 | 설명 |
|--------|------|
| test_llm_failure_fallback_to_original | LLM 실패 시 원본 fallback |

#### TestStateUpdate (2개)
| 테스트 | 설명 |
|--------|------|
| test_returns_only_required_fields | 필수 필드만 반환 |
| test_thoughts_returns_own_only | thoughts 자기 것만 반환 (reducer 병합) |

#### TestRewriterPromptGuidelines (5개)
| 테스트 | 설명 |
|--------|------|
| test_prompt_has_semantic_preservation | 의미 보존 지침 포함 |
| test_prompt_has_minimal_edit_principle | 최소 수정 원칙 포함 |
| test_prompt_has_no_keyword_addition_rule | 키워드 임의 추가 금지 규칙 포함 |
| test_prompt_has_new_topic_isolation | 새 주제 격리 지침 포함 |
| test_prompt_has_at_least_three_guidelines | 지침 3개 이상 포함 |

#### TestShortQueries (3개)
| 테스트 | 설명 |
|--------|------|
| test_single_char_query | 단일 문자 쿼리 |
| test_short_greeting_query | 짧은 인사 쿼리 |
| test_hello_query | "안녕" 쿼리 |

---

### 11. test_rag_client.py (RAG 클라이언트) — 24개

RAG 문서 검색 클라이언트 및 검색 요청 body 테스트.

#### TestDocument (3개)
| 테스트 | 설명 |
|--------|------|
| test_document_creation | Document 생성 |
| test_document_with_empty_metadata | 빈 metadata |
| test_document_score_range | score 범위 확인 |

#### TestMockRAGClient (5개)
| 테스트 | 설명 |
|--------|------|
| test_search_returns_documents | 검색 결과 반환 |
| test_search_returns_all_documents | 전체 샘플 문서 반환 (top_k 없음) |
| test_search_documents_have_valid_structure | 문서 구조 확인 |
| test_search_returns_sorted_by_score | score 정렬 확인 |
| test_mock_client_implements_protocol | 프로토콜 구현 확인 |

#### TestRAGClient (5개)
| 테스트 | 설명 |
|--------|------|
| test_rag_client_creation_with_defaults | 기본값으로 생성 |
| test_rag_client_creation_with_custom_params | 커스텀 파라미터 |
| test_rag_client_search_connection_error | 연결 실패 시 BusinessException |
| test_rag_client_implements_protocol | 프로토콜 구현 확인 |
| test_rag_client_context_manager | 컨텍스트 매니저 |

#### TestGetRAGClient (2개)
| 테스트 | 설명 |
|--------|------|
| test_get_mock_rag_client_when_use_mock_true | USE_MOCK=true → Mock |
| test_get_real_rag_client_when_use_mock_false | USE_MOCK=false → Real |

#### TestRAGClientSearchBody (4개)
| 테스트 | 설명 |
|--------|------|
| test_search_body_includes_user_depts_array | 요청 body에 user_depts 포함 |
| test_search_body_includes_excluded_docs | 요청 body에 excluded_docs 포함 |
| test_search_body_excludes_empty_excluded_docs | 빈 excluded_docs는 body에서 제외 |
| test_search_body_excludes_none_excluded_docs | None excluded_docs는 body에서 제외 |

#### TestFormatDocumentsForContext (5개)
| 테스트 | 설명 |
|--------|------|
| test_format_single_document | 단일 문서 포맷 |
| test_format_multiple_documents | 다중 문서 포맷 |
| test_format_empty_documents | 빈 문서 목록 |
| test_format_preserves_content | 내용 보존 확인 |
| test_format_excludes_metadata | metadata 미포함 확인 (`<document>` 태그만) |

---

### 12. test_retriever_synthesizer.py (Retriever/Synthesizer) — 27개

RAG 검색 및 답변 생성 노드 테스트.

#### TestSynthesizerPrompt (5개)
| 테스트 | 설명 |
|--------|------|
| test_prompt_is_chat_prompt_template | ChatPromptTemplate 타입 |
| test_prompt_has_required_variables | 필수 변수 포함 |
| test_prompt_format_produces_messages | 메시지 생성 확인 |
| test_prompt_contains_instructions | 지시사항 포함 |
| test_no_context_response_defined | NO_CONTEXT_RESPONSE 정의 |

#### TestRetrieverNode (8개)
| 테스트 | 설명 |
|--------|------|
| test_retriever_calls_rag_client | RAG 클라이언트 호출 |
| test_retriever_uses_standalone_query | standalone_query 사용 |
| test_retriever_fallback_to_original_query | 원본 query fallback |
| test_retriever_formats_documents | 문서 포맷팅 |
| test_retriever_empty_results | 빈 결과 시 `retrieval_status="empty"` |
| test_retriever_thought_message_with_results | 결과 있을 때 thought |
| test_retriever_error_handling | 검색 실패 시 `retrieval_status="error"` |
| test_retriever_skip_rag_status | SKIP_RAG 시 `retrieval_status="skipped"` |

#### TestSynthesizerNodeNoContext (2개)
| 테스트 | 설명 |
|--------|------|
| test_no_context_returns_fixed_message | 컨텍스트 없을 때 응답 반환 |
| test_no_context_calls_llm | 컨텍스트 없어도 `synthesizer-no-rag` 프롬프트로 LLM 호출 |

#### TestSynthesizerNodeWithContext (3개)
| 테스트 | 설명 |
|--------|------|
| test_with_context_calls_llm | 컨텍스트 있으면 LLM 호출 |
| test_llm_called_with_primary_role | primary 역할 사용 |
| test_thought_message_with_context | 컨텍스트 있을 때 thought |

#### TestSynthesizerOutputParsing (2개)
| 테스트 | 설명 |
|--------|------|
| test_response_stripped | 응답 strip 처리 |
| test_empty_response_fallback | 빈 응답 fallback |

#### TestSynthesizerErrorHandling (2개)
| 테스트 | 설명 |
|--------|------|
| test_llm_failure_returns_error_message | LLM 실패 시 에러 메시지 |
| test_unexpected_error_handling | 예상치 못한 에러 처리 |

#### TestGraphStructure (4개)
| 테스트 | 설명 |
|--------|------|
| test_graph_includes_retriever | retriever 노드 포함 |
| test_graph_edge_rewriter_to_retriever | rewriter→retriever 엣지 |
| test_graph_edge_retriever_to_synthesizer | retriever→synthesizer 엣지 |
| test_graph_node_order | 노드 순서 확인 |

#### TestContextFormatting (1개)
| 테스트 | 설명 |
|--------|------|
| test_context_joined_with_newlines | 컨텍스트 줄바꿈 연결 |

---

### 13. test_router.py (Router 노드) — 44개

의도 분류 노드 테스트. 사용자 질문을 `rag`, `tool`, `both`, `direct` 중 하나로 분류하고,
SKIP 플래그로 가용 경로를 제한한다.

#### TestParseRoute (12개)
| 테스트 | 설명 |
|--------|------|
| test_parse_rag | "rag" 파싱 |
| test_parse_tool | "tool" 파싱 |
| test_parse_both | "both" 파싱 |
| test_parse_direct | "direct" 파싱 |
| test_parse_with_whitespace | 공백 포함 파싱 |
| test_parse_uppercase | 대문자 파싱 |
| test_parse_mixed_case | 혼합 대소문자 파싱 |
| test_parse_embedded_route | 텍스트 내 라우트 추출 |
| test_parse_invalid_defaults_to_rag | 유효하지 않은 입력 → rag 기본값 |
| test_parse_empty_defaults_to_rag | 빈 입력 → rag 기본값 |
| test_parse_unavailable_route_falls_back | 가용하지 않은 경로 → 기본값 |
| test_parse_unavailable_both_falls_back | 가용하지 않은 both → 기본값 |

#### TestGetDefaultRoute (3개)
| 테스트 | 설명 |
|--------|------|
| test_default_with_rag_available | rag 가용 시 기본값 rag |
| test_default_with_only_tool | tool만 가용 시 기본값 tool |
| test_default_with_only_direct | direct만 가용 시 기본값 direct |

#### TestRouterNode (10개)
| 테스트 | 설명 |
|--------|------|
| test_router_returns_route_and_thoughts | route + thoughts 반환 |
| test_router_rag_route | rag 라우팅 |
| test_router_tool_route | tool 라우팅 |
| test_router_both_route | both 라우팅 |
| test_router_fallback_on_invalid_response | 유효하지 않은 응답 시 fallback |
| test_router_fallback_on_exception | 예외 시 fallback |
| test_router_uses_standalone_query | standalone_query 사용 확인 |
| test_router_thoughts_self_only | thoughts 자기 것만 반환 |
| test_router_uses_fast_role | fast 역할 사용 확인 |
| test_router_direct_route | direct 라우팅 |

#### TestRouterSkipFlags (5개)
| 테스트 | 설명 |
|--------|------|
| test_skip_tool_excludes_tool_routes | SKIP_TOOL 시 tool/both 제외 |
| test_skip_rag_excludes_rag_routes | SKIP_RAG 시 rag/both 제외 |
| test_skip_both_returns_direct | rag+tool 모두 스킵 시 direct |
| test_skip_direct_excludes_direct_route | SKIP_DIRECT 시 direct 제외 |
| test_skip_all_falls_back_to_rag | 전부 스킵 시 rag fallback |

#### TestGetAvailableRoutes (7개)
| 테스트 | 설명 |
|--------|------|
| test_all_enabled | 전체 활성화 시 4개 경로 |
| test_skip_tool | SKIP_TOOL 매트릭스 |
| test_skip_rag | SKIP_RAG 매트릭스 |
| test_skip_both_rag_tool | SKIP_RAG + SKIP_TOOL 매트릭스 |
| test_skip_direct | SKIP_DIRECT 매트릭스 |
| test_skip_direct_and_tool | SKIP_DIRECT + SKIP_TOOL 매트릭스 |
| test_skip_all | 전체 스킵 매트릭스 |

#### TestRouterPromptContent (4개)
| 테스트 | 설명 |
|--------|------|
| test_prompt_has_keyword_matching_section | 1단계 키워드 매칭 섹션 포함 |
| test_prompt_has_intent_analysis_section | 2단계 의도 분석 섹션 포함 |
| test_prompt_has_few_shot_examples | few-shot 예시 포함 |
| test_prompt_excludes_unavailable_routes | 가용하지 않은 경로는 프롬프트에서 제외 |

#### TestRouteByIntent (3개)
| 테스트 | 설명 |
|--------|------|
| test_direct_route | direct → synthesizer 직행 |
| test_both_route_fan_out | both → `["rag", "tool"]` fan-out |
| test_rag_route | rag → retriever |

---

### 14. test_tool_client.py (Tool 클라이언트) — 30개

Tool Server 클라이언트 (Mock + Real) 테스트.

#### TestToolDefinition (2개)
| 테스트 | 설명 |
|--------|------|
| test_tool_definition_creation | ToolDefinition 생성 |
| test_tool_definition_json_schema_parameters | JSON 스키마 파라미터 |

#### TestToolResult (3개)
| 테스트 | 설명 |
|--------|------|
| test_tool_result_success | 성공 결과 |
| test_tool_result_failure | 실패 결과 |
| test_tool_result_default_error | 기본 에러 |

#### TestToolClientProtocol (3개)
| 테스트 | 설명 |
|--------|------|
| test_mock_client_implements_protocol | 프로토콜 구현 확인 |
| test_protocol_has_list_tools | list_tools 메서드 존재 |
| test_protocol_has_call_tool | call_tool 메서드 존재 |

#### TestMockToolClient (9개)
| 테스트 | 설명 |
|--------|------|
| test_list_tools_returns_tools | 도구 목록 반환 |
| test_list_tools_contains_get_weather | get_weather 도구 포함 |
| test_list_tools_contains_calculate | calculate 도구 포함 |
| test_call_tool_get_weather_seoul | 서울 날씨 조회 |
| test_call_tool_get_weather_default_location | 기본 위치 날씨 |
| test_call_tool_calculate | 계산 도구 실행 |
| test_call_tool_unknown_tool | 알 수 없는 도구 |
| test_call_tool_missing_required_argument_location | 필수 인자(location) 누락 |
| test_call_tool_missing_required_argument_expression | 필수 인자(expression) 누락 |

#### TestToolClient (8개)
| 테스트 | 설명 |
|--------|------|
| test_tool_client_init_default_settings | 기본 설정으로 초기화 |
| test_tool_client_init_custom_settings | 커스텀 설정으로 초기화 |
| test_list_tools_connection_error | 연결 에러 처리 |
| test_call_tool_connection_error | 연결 에러 처리 |
| test_context_manager | 컨텍스트 매니저 |
| test_close | 클라이언트 종료 |
| test_tool_client_has_lock | Lock 보유 확인 |
| test_get_client_creates_httpx_client | httpx 클라이언트 생성 |

#### TestGetToolClient (3개)
| 테스트 | 설명 |
|--------|------|
| test_get_mock_client_when_use_mock_true | USE_MOCK=true → Mock |
| test_get_real_client_when_use_mock_false | USE_MOCK=false → Real |
| test_factory_uses_settings_for_real_client | 실제 클라이언트 설정 사용 |

#### TestToolConfigSettings (2개)
| 테스트 | 설명 |
|--------|------|
| test_tool_settings_defaults | 기본 설정값 |
| test_tool_settings_can_be_overridden | 설정 오버라이드 |

---

### 15. test_tool_executor.py (Tool Executor 노드) — 14개

도구 실행 노드 테스트. 도구 선택, 인자 구성, 실행 처리.

#### TestSelectTool (3개)
| 테스트 | 설명 |
|--------|------|
| test_select_by_name_match | 이름 매칭으로 도구 선택 |
| test_select_by_name_calculate | calculate 도구 선택 |
| test_select_default_first_tool | 기본값: 첫 번째 도구 선택 |

#### TestBuildArguments (3개)
| 테스트 | 설명 |
|--------|------|
| test_weather_arguments | 날씨 도구 인자 구성 |
| test_calculate_arguments | 계산 도구 인자 구성 |
| test_unknown_tool_arguments | 알 수 없는 도구 인자 |

#### TestExtractLocation (3개)
| 테스트 | 설명 |
|--------|------|
| test_extract_seoul | "서울" 추출 |
| test_extract_busan | "부산" 추출 |
| test_default_seoul | 기본값 "서울" |

#### TestToolExecutorNode (5개)
| 테스트 | 설명 |
|--------|------|
| test_tool_executor_returns_context_and_thoughts | context + thoughts 반환 |
| test_tool_executor_empty_tools | 빈 도구 목록 처리 |
| test_tool_executor_tool_failure | 도구 실패 처리 |
| test_tool_executor_exception_handling | 예외 처리 |
| test_tool_executor_thoughts_self_only | thoughts 자기 것만 반환 |

---

### 16. test_tracing.py (LangFuse 트레이싱) — 29개

LangFuse 통합 트레이싱 및 cross-service trace context 추출 테스트.

#### TestTracingManagerDisabled (4개)
| 테스트 | 설명 |
|--------|------|
| test_tracing_disabled_when_no_keys | 키 없으면 비활성화 |
| test_tracing_logs_warning_when_disabled | 비활성화 시 경고 로그 |
| test_get_callback_handler_returns_none_when_disabled | 비활성화 시 None 반환 |
| test_get_callbacks_returns_empty_list_when_disabled | 비활성화 시 빈 리스트 |

#### TestTracingManagerEnabled (3개)
| 테스트 | 설명 |
|--------|------|
| test_tracing_enabled_with_valid_keys | 유효한 키로 활성화 |
| test_get_callback_handler_creates_handler | 핸들러 생성 |
| test_get_callbacks_returns_list_with_handler | 핸들러 리스트 반환 |

#### TestTracingManagerMetadata (2개)
| 테스트 | 설명 |
|--------|------|
| test_get_langfuse_config_includes_session_id | session_id 포함 |
| test_get_langfuse_config_includes_tags | tags 포함 |

#### TestTracingInitialization (2개)
| 테스트 | 설명 |
|--------|------|
| test_initialize_only_runs_once | 초기화 1회만 실행 |
| test_enabled_property_triggers_initialization | enabled 속성으로 초기화 |

#### TestTraceContext (2개)
| 테스트 | 설명 |
|--------|------|
| test_default_values | TraceContext 기본값 |
| test_with_values | TraceContext 값 지정 |

#### TestFindLangfuseHandler (5개)
| 테스트 | 설명 |
|--------|------|
| test_finds_sdk_v3_handler | SDK v3 핸들러 탐색 |
| test_finds_sdk_v2_handler | SDK v2 핸들러 탐색 |
| test_skips_non_langfuse_handlers | 비-LangFuse 핸들러 건너뛰기 |
| test_returns_none_for_empty_list | 빈 리스트 시 None |
| test_handles_non_iterable | 순회 불가 입력 처리 |

#### TestExtractTraceId (5개)
| 테스트 | 설명 |
|--------|------|
| test_sdk_v2_get_trace_id | SDK v2 get_trace_id() |
| test_sdk_v2_trace_id_attr | SDK v2 trace_id 속성 |
| test_sdk_v3_last_trace_id | SDK v3 last_trace_id |
| test_sdk_v3_last_trace_id_none | SDK v3 last_trace_id None |
| test_no_trace_id_available | trace_id 미확보 시 처리 |

#### TestExtractTraceContext (6개)
| 테스트 | 설명 |
|--------|------|
| test_empty_config | 빈 config 처리 |
| test_no_callbacks | callbacks 없을 때 처리 |
| test_extracts_trace_id_from_handler | 핸들러에서 trace_id 추출 |
| test_extracts_both_trace_id_and_observation_id | trace_id + observation_id 추출 |
| test_observation_id_none_when_no_parent_run | parent run 없을 때 None |
| test_observation_id_none_when_run_not_found | run 미발견 시 None |

---

### 17. test_workflow_graph.py (워크플로우 그래프) — 28개

LangGraph 워크플로우 테스트.

#### TestAgentState (5개)
| 테스트 | 설명 |
|--------|------|
| test_create_initial_state_required_fields | 필수 필드로 상태 생성 |
| test_create_initial_state_with_history | history 포함 상태 생성 |
| test_initial_state_default_values | 기본값 확인 |
| test_create_initial_state_with_user_depts_and_excluded_docs | user_depts/excluded_docs 포함 생성 |
| test_agent_state_fields_documented | 필드 문서화 확인 |

#### TestRewriterNode (3개)
| 테스트 | 설명 |
|--------|------|
| test_rewriter_returns_standalone_query | standalone_query 반환 |
| test_rewriter_updates_thoughts | thoughts 업데이트 |
| test_rewriter_with_history | history 있는 경우 |

#### TestSynthesizerNode (3개)
| 테스트 | 설명 |
|--------|------|
| test_synthesizer_returns_response | response 반환 |
| test_synthesizer_updates_thoughts | thoughts 업데이트 |
| test_synthesizer_with_context | context 있는 경우 |

#### TestStateGraph (4개)
| 테스트 | 설명 |
|--------|------|
| test_build_graph_returns_state_graph | StateGraph 반환 |
| test_graph_has_required_nodes | 필수 노드 포함 |
| test_compile_graph_returns_runnable | 컴파일 후 Runnable |
| test_get_compiled_graph_singleton | 싱글톤 확인 |

#### TestWorkflowExecution (5개)
| 테스트 | 설명 |
|--------|------|
| test_run_workflow_basic | 기본 워크플로우 실행 |
| test_run_workflow_state_passing | 상태 전달 확인 |
| test_run_workflow_thoughts_accumulated | thoughts 누적 |
| test_run_workflow_with_history | history 포함 실행 |
| test_run_workflow_preserves_session_id | session_id 보존 |

#### TestErrorHandling (2개)
| 테스트 | 설명 |
|--------|------|
| test_initial_state_error_is_none | 초기 상태 error None |
| test_workflow_completes_without_error | 에러 없이 완료 |

#### TestNegativeCases (6개)
| 테스트 | 설명 |
|--------|------|
| test_empty_query_raises_error | 빈 query 에러 |
| test_whitespace_query_raises_error | 공백 query 에러 |
| test_empty_session_id_raises_error | 빈 session_id 에러 |
| test_whitespace_session_id_raises_error | 공백 session_id 에러 |
| test_long_query_handled | 긴 query 처리 |
| test_unicode_query_handled | 유니코드 query 처리 |

> `TestWorkflowExecution` / `TestNegativeCases`는 `graph.run_workflow()`를 대상으로 합니다.
> 이 함수는 현재 프로덕션 경로에서 미사용이며(`chat.py`가 `astream_events`를 직접 사용),
> `user_depts` 등 신규 필드가 반영되어 있지 않습니다.

---

## 통합 테스트 상세

### test_chat_integration.py (Chat API E2E) — 10개

실제 LLM 서버를 사용한 Chat API 통합 테스트.

#### TestChatSSEEndpoint (2개)
| 테스트 | 설명 |
|--------|------|
| test_chat_endpoint_returns_sse | SSE 응답 반환 확인 |
| test_chat_done_event | done 이벤트 수신 확인 |

#### TestChatEventTypes (3개)
| 테스트 | 설명 |
|--------|------|
| test_chat_message_streaming | message 토큰 스트리밍 |
| test_chat_thought_events | thought 이벤트 확인 |
| test_event_format | 이벤트 포맷 확인 |

#### TestChatFullWorkflow (3개)
| 테스트 | 설명 |
|--------|------|
| test_full_chat_workflow | 전체 워크플로우 E2E |
| test_chat_with_history | history 포함 요청 |
| test_chat_with_user_id | user_id 포함 요청 |

#### TestChatRequestSchema (2개)
| 테스트 | 설명 |
|--------|------|
| test_required_fields | 필수 필드 검증 |
| test_optional_fields | 선택 필드 검증 |

---

### test_langfuse_integration.py (LangFuse 트레이싱) — 9개

#### TestLangFuseConnection (3개)
| 테스트 | 설명 |
|--------|------|
| test_langfuse_settings_loaded | LangFuse 설정 로드 확인 |
| test_tracing_manager_enabled | TracingManager 활성화 |
| test_callback_handler_created | CallbackHandler 생성 |

#### TestLangFuseTracing (3개)
| 테스트 | 설명 |
|--------|------|
| test_llm_invoke_traced | LLM invoke 트레이싱 |
| test_query_rewriter_traced | Query Rewriter 트레이싱 |
| test_full_workflow_traced | 전체 워크플로우 트레이싱 |

#### TestLangFuseMetadata (1개)
| 테스트 | 설명 |
|--------|------|
| test_session_id_in_trace | trace에 session_id 포함 |

#### TestCrossServiceTraceId (2개)
| 테스트 | 설명 |
|--------|------|
| test_rag_route_headers | RAG 요청 시 트레이싱 헤더 전달 |
| test_tool_route_headers | Tool 요청 시 트레이싱 헤더 전달 |

---

### test_prompt_management.py (프롬프트 관리) — 9개

LangFuse에 프롬프트가 `production` 라벨로 등록되어 있어야 합니다.

#### TestLangFusePromptFetch (4개)
| 테스트 | 설명 |
|--------|------|
| test_fetch_rewriter_prompt | rewriter 프롬프트 fetch |
| test_fetch_synthesizer_prompt | synthesizer 프롬프트 fetch |
| test_fetch_router_prompt | router 프롬프트 fetch |
| test_prefetch_all | 전체 프롬프트 pre-fetch |

#### TestLangFusePromptFallback (2개)
| 테스트 | 설명 |
|--------|------|
| test_fallback_when_langfuse_disabled | 비활성 시 fallback 동작 |
| test_fallback_with_wrong_key | 잘못된 키로 fetch 실패 시 fallback |

#### TestPromptNodeIntegration (3개)
| 테스트 | 설명 |
|--------|------|
| test_rewriter_node_uses_langfuse_prompt | rewriter 노드가 LangFuse 프롬프트 사용 |
| test_synthesizer_node_uses_langfuse_prompt | synthesizer 노드가 LangFuse 프롬프트 사용 |
| test_router_build_with_langfuse | router 프롬프트 동적 빌드 |

---

### test_workflow_routes.py (워크플로우 라우트) — 5개

#### TestRAGRoute (2개)
| 테스트 | 설명 |
|--------|------|
| test_rag_route_returns_documents | RAG 라우트 문서 반환 |
| test_rag_route_thoughts_chain | RAG 라우트 thoughts 체인 |

#### TestToolRoute (1개)
| 테스트 | 설명 |
|--------|------|
| test_tool_route_executes_summary | Tool 라우트 실행 요약 |

#### TestBothRoute (2개)
| 테스트 | 설명 |
|--------|------|
| test_fanout_parallel_execution | fan-out 병렬 실행 |
| test_state_reducer_merges_thoughts | State Reducer thoughts 병합 |
