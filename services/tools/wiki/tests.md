# 테스트 문서

## 개요

TOL Server의 테스트 문서입니다.

- **테스트 프레임워크**: pytest, pytest-asyncio, respx
- **총 테스트 수**: **218개** (단위 216 + E2E 2)
- **Python 버전**: 3.11+

## 실행 방법

### 단위 테스트

```bash
# 전체 실행
pytest tests/

# 상세 출력
pytest tests/ -v

# 특정 파일
pytest tests/test_trace_id.py -v

# 특정 클래스
pytest tests/test_trace_id.py::TestTraceIDMiddleware -v

# 특정 테스트 함수
pytest tests/test_trace_id.py::TestTraceIDMiddleware::test_generates_trace_id_when_missing -v

# 패턴 필터
pytest tests/ -k "test_trace"

# 커버리지
pytest tests/ --cov=src --cov-report=term-missing

# 목록만 확인
pytest tests/ --collect-only -q
```

### E2E 테스트

Langfuse 실환경 연결 테스트. `LANGFUSE_PUBLIC_KEY` 환경변수 미설정 시 자동 스킵.

```bash
pytest tests/test_langfuse_e2e.py -v
```

---

## 테스트 파일 목록

| 파일 | 테스트 수 | 대상 모듈 |
|------|----------|----------|
| test_config.py | 16 | YAML/ENV 설정 로더 |
| test_models.py | 22 | Role-Based 모델 매핑, fallback 체인 |
| test_prompt_engine.py | 12 | 프롬프트 템플릿 렌더링 |
| test_trace_id.py | 22 | Trace-ID 미들웨어, Langfuse root span |
| test_langfuse.py | 15 | create_span, create_generation, ManagedSpan |
| test_langfuse_e2e.py | 2 | Langfuse 실환경 연결 (E2E) |
| test_provider.py | 36 | GatewayProvider, invoke, failover |
| test_graceful_degradation.py | 5 | LLM 체인 소진 시 503 응답 |
| test_summary_endpoint.py | 27 | POST /v1/summary 라우터 + 서비스 |
| test_scoping.py | 17 | Scope 필터링, InvalidScopeError |
| test_tools_endpoint.py | 15 | GET /v1/tools, OpenAI Spec 응답 |
| test_proxy_service.py | 27 | 외부 API 프록시, 재시도, Langfuse span |
| test_catch_all_handler.py | 2 | catch-all 예외 핸들러 |
| **합계** | **218** | |

---

## 테스트 상세

### 1. test_config.py (설정 로더)

설정 로더 (`config.yaml` + `.env`) 테스트.

#### TestSettings (4개)
| 테스트 | 설명 |
|--------|------|
| test_default_values | 기본값 확인 |
| test_env_override | 환경변수 오버라이드 |
| test_is_production | is_production 속성 |
| test_is_development | is_development 속성 |

#### TestDeepMerge (3개)
| 테스트 | 설명 |
|--------|------|
| test_simple_merge | 단순 병합 |
| test_nested_merge | 중첩 키 병합 |
| test_base_unchanged | base dict 변경 없음 확인 |

#### TestLoadConfig (2개)
| 테스트 | 설명 |
|--------|------|
| test_load_config_returns_dict | config.yaml 로드 → dict 반환 |
| test_app_name_exists | app.name 필드 존재 |

#### TestGetConfigValue (4개)
| 테스트 | 설명 |
|--------|------|
| test_dot_notation | dot notation 접근 |
| test_nested_key | 중첩 키 접근 |
| test_missing_key_default | 없는 키 → 기본값 |
| test_missing_key_none | 없는 키 → None |

#### TestEnvironmentOverride (3개)
| 테스트 | 설명 |
|--------|------|
| test_development_override | development 오버라이드 적용 |
| test_production_override | production 오버라이드 적용 |
| test_base_config_preserved | 오버라이드 시 base 설정 보존 |

---

### 2. test_models.py (모델 매핑)

Role-Based 모델 매핑 (`models.yaml`) 테스트.

#### TestLoadModelsConfig (7개)
| 테스트 | 설명 |
|--------|------|
| test_returns_models_config | ModelsConfig 반환 |
| test_has_roles | roles 존재 |
| test_has_primary_role | primary 역할 존재 |
| test_has_fast_role | fast 역할 존재 |
| test_has_reasoning_role | reasoning 역할 존재 |
| test_default_role | default_role 확인 |
| test_fallback_message | fallback_message 확인 |

#### TestModelRole (3개)
| 테스트 | 설명 |
|--------|------|
| test_primary_role_info | primary 역할 정보 |
| test_fast_role_info | fast 역할 정보 |
| test_reasoning_role_info | reasoning 역할 정보 |

#### TestGetModel (3개)
| 테스트 | 설명 |
|--------|------|
| test_get_model_primary | primary 모델명 조회 |
| test_get_model_fast | fast 모델명 조회 |
| test_get_model_nonexistent | 없는 역할 → None |

#### TestGetFallbackChain (4개)
| 테스트 | 설명 |
|--------|------|
| test_primary_fallback_chain | primary 체인 순회 |
| test_fast_fallback_chain | fast 체인 순회 |
| test_reasoning_fallback_chain | reasoning 체인 순회 |
| test_nonexistent_fallback_chain | 없는 역할 체인 |

#### TestHelperFunctions (5개)
| 테스트 | 설명 |
|--------|------|
| test_get_model_for_role_primary | get_model_for_role("primary") |
| test_get_model_for_role_default | get_model_for_role(None) → default |
| test_get_model_for_role_nonexistent | 없는 역할 에러 |
| test_get_fallback_chain_helper | get_fallback_chain 헬퍼 |
| test_get_fallback_chain_default | 기본 역할 체인 |

---

### 3. test_prompt_engine.py (프롬프트 엔진)

프롬프트 템플릿 엔진 테스트.

#### TestPromptsConfig (3개)
| 테스트 | 설명 |
|--------|------|
| test_prompt_template_creation | PromptTemplate 생성 |
| test_prompts_config_get_template | 템플릿 조회 |
| test_prompt_template_frozen | frozen dataclass 확인 |

#### TestLoadPromptsConfig (4개)
| 테스트 | 설명 |
|--------|------|
| test_load_prompts_config_success | prompts.yaml 로드 성공 |
| test_summary_template_has_required_fields | summary 템플릿 필수 필드 |
| test_file_not_found_raises_error | 파일 없음 에러 |
| test_missing_system_field_raises_error | system 필드 누락 에러 |

#### TestRenderSystemPrompt (5개)
| 테스트 | 설명 |
|--------|------|
| test_render_with_config_variables | 설정 변수로 렌더링 |
| test_render_with_override | 오버라이드 값 렌더링 |
| test_render_key_extraction | key_extraction 템플릿 렌더링 |
| test_nonexistent_template_raises_error | 없는 템플릿 에러 |
| test_missing_variable_raises_error | 누락 변수 에러 |

---

### 4. test_trace_id.py (Trace-ID 미들웨어)

Trace-ID 미들웨어 + Langfuse root span 테스트.

#### TestGenerateTraceId (3개)
| 테스트 | 설명 |
|--------|------|
| test_returns_string | 문자열 반환 |
| test_returns_valid_uuid | 유효한 UUID 형식 |
| test_returns_unique_ids | 매 호출 고유 ID |

#### TestGetTraceId (2개)
| 테스트 | 설명 |
|--------|------|
| test_returns_none_by_default | 기본값 None |
| test_returns_set_value | 설정된 값 반환 |

#### TestTraceIDMiddleware (5개)
| 테스트 | 설명 |
|--------|------|
| test_generates_trace_id_when_missing | 헤더 없으면 자동 생성 |
| test_uses_provided_trace_id | 전달된 Trace-ID 사용 |
| test_generated_header_flag | Generated 플래그 설정 |
| test_no_generated_flag_when_provided | 전달 시 Generated 플래그 없음 |
| test_trace_id_header_name | 헤더 이름 상수 확인 |

#### TestHealthEndpointWithTraceID (2개)
| 테스트 | 설명 |
|--------|------|
| test_health_returns_trace_id | /health 응답에 Trace-ID 포함 |
| test_health_preserves_custom_trace_id | 커스텀 Trace-ID 보존 |

#### TestHandleRequestLangfuseBranch (6개)
| 테스트 | 설명 |
|--------|------|
| test_no_langfuse_client_skips_observation | Langfuse 클라이언트 없음 → 스킵 |
| test_valid_uuid_trace_id_triggers_root_span | UUID Trace-ID → root span 생성 |
| test_health_endpoint_skips_langfuse | /health → Langfuse 스킵 |
| test_no_trace_header_skips_langfuse | 헤더 없음 → Langfuse 스킵 |
| test_32char_hex_trace_id_accepted | 32자 hex ID 허용 |
| test_non_hex_trace_id_skips_observation | 비hex ID → observation 스킵 |

#### TestParentIdHeader (3개)
| 테스트 | 설명 |
|--------|------|
| test_parent_id_header_constant | X-LF-Parent-Id 상수 확인 |
| test_parent_id_passed_to_trace_context | parent_id → trace_context 전달 |
| test_no_parent_id_works_without_parent_span_id | parent_id 없이 정상 동작 |

#### TestStripAsRoot (1개)
| 테스트 | 설명 |
|--------|------|
| test_strip_as_root_called | as_root=False 설정 검증 |

---

### 5. test_langfuse.py (Langfuse 모듈)

Langfuse 클라이언트, span, generation 테스트.

#### TestGetLangfuseClient (3개)
| 테스트 | 설명 |
|--------|------|
| test_returns_none_when_no_keys | 환경변수 없음 → None |
| test_returns_client_when_keys_provided | 키 있음 → 클라이언트 반환 |
| test_returns_none_on_init_error | 초기화 에러 → None |

#### TestCreateSpan (5개)
| 테스트 | 설명 |
|--------|------|
| test_returns_none_when_no_trace_context | trace_context 없음 → None |
| test_returns_none_when_no_client | 클라이언트 없음 → None |
| test_creates_managed_span_with_trace_context | ManagedSpan 정상 생성 |
| test_managed_span_end_calls_cm_exit | end() 호출 시 cm 정리 |
| test_returns_none_on_error | 예외 시 → None |

#### TestCreateGeneration (4개)
| 테스트 | 설명 |
|--------|------|
| test_returns_none_when_no_trace_context | trace_context 없음 → None |
| test_returns_none_when_no_client | 클라이언트 없음 → None |
| test_creates_generation_successfully | generation 정상 생성 |
| test_returns_none_on_error | 예외 시 → None |

#### TestFlushLangfuse (3개)
| 테스트 | 설명 |
|--------|------|
| test_does_nothing_when_no_client | 클라이언트 없음 → no-op |
| test_flushes_client | 정상 flush |
| test_handles_flush_error | flush 에러 처리 |

---

### 6. test_langfuse_e2e.py (Langfuse E2E)

Langfuse 실환경 연결 테스트. `LANGFUSE_PUBLIC_KEY` 미설정 시 자동 스킵.

#### TestLangfuseE2EConnection (2개)
| 테스트 | 설명 |
|--------|------|
| test_client_initializes_with_real_credentials | 실제 키로 클라이언트 초기화 |
| test_create_span_without_trace_context_returns_none | trace_context 없이 create_span → None |

---

### 7. test_provider.py (GatewayProvider)

GatewayLLMProvider 테스트.

#### TestBaseLLMProvider (5개)
| 테스트 | 설명 |
|--------|------|
| test_cannot_instantiate_abc | ABC 직접 인스턴스화 불가 |
| test_subclass_must_implement_invoke | invoke 구현 필수 |
| test_subclass_must_implement_invoke_with_failover | invoke_with_failover 구현 필수 |
| test_gateway_provider_is_subclass | Gateway는 Base의 서브클래스 |
| test_gateway_provider_isinstance | isinstance 확인 |

#### TestGatewayInvoke (5개)
| 테스트 | 설명 |
|--------|------|
| test_invoke_success | 정상 호출 성공 |
| test_invoke_sends_correct_payload | 올바른 페이로드 전송 |
| test_invoke_sends_auth_header | 인증 헤더 전송 |
| test_invoke_fast_role | fast 역할 호출 |
| test_invoke_invalid_role | 유효하지 않은 역할 에러 |

#### TestGatewayErrors (3개)
| 테스트 | 설명 |
|--------|------|
| test_invoke_http_401_error | HTTP 401 에러 처리 |
| test_invoke_http_429_error | HTTP 429 에러 처리 |
| test_invoke_http_500_error | HTTP 500 에러 처리 |

#### TestGatewayTimeout (2개)
| 테스트 | 설명 |
|--------|------|
| test_invoke_timeout | 요청 타임아웃 |
| test_invoke_connect_timeout | TCP 연결 타임아웃 |

#### TestGatewayClose (3개)
| 테스트 | 설명 |
|--------|------|
| test_close_after_use | 사용 후 리소스 정리 |
| test_close_without_use | 미사용 시 정리 |
| test_client_lazy_initialization | 클라이언트 지연 초기화 |

#### TestGatewayInvokeWithFailover (15개)
| 테스트 | 설명 |
|--------|------|
| test_success_on_primary_no_failover | primary 성공 → failover 없음 |
| test_failover_primary_to_fast | primary 실패 → fast 전환 |
| test_failover_reasoning_chain | reasoning 체인 순회 |
| test_chain_exhausted_raises_runtime_error | 체인 소진 시 에러 |
| test_timeout_triggers_failover | 타임아웃 → failover |
| test_connect_error_triggers_failover | 연결 에러 → failover |
| test_max_retries_per_role | 역할별 최대 재시도 |
| test_chain_exhausted_with_retries_raises | 재시도 포함 체인 소진 |
| test_empty_chain_raises_value_error | 빈 체인 → ValueError |
| test_accepts_trace_metadata | trace metadata 전달 |
| test_fast_role_no_fallback | fast 역할 fallback 없음 |
| test_4xx_not_retried | 4xx → 재시도 없이 전파 |
| test_429_triggers_failover | 429 → failover |
| test_langfuse_span_created_on_success | 성공 시 Langfuse span 생성 |
| test_langfuse_span_records_failover_error | failover 시 span 에러 기록 |

#### TestProviderDI (3개)
| 테스트 | 설명 |
|--------|------|
| test_create_gateway_provider | GatewayProvider 생성 |
| test_get_llm_provider_returns_singleton | 싱글톤 반환 |
| test_get_llm_provider_returns_base_type | Base 타입 반환 |

---

### 8. test_graceful_degradation.py (Graceful Degradation)

LLM 체인 소진 시 Graceful Degradation 테스트.

#### TestLLMProviderError (3개)
| 테스트 | 설명 |
|--------|------|
| test_basic_creation | 기본 예외 생성 |
| test_with_role_and_chain | role, chain 속성 보존 |
| test_is_exception | Exception 상속 확인 |

#### TestGracefulDegradationHandler (2개)
| 테스트 | 설명 |
|--------|------|
| test_handler_returns_503_with_tol_response | HTTP 503 + TOL020130 응답 |
| test_handler_response_data_is_null | data=null 확인 |

---

### 9. test_summary_endpoint.py (Summary API)

POST /v1/summary 라우터 + 서비스 테스트.

#### TestSummaryEndpointSuccess (7개)
| 테스트 | 설명 |
|--------|------|
| test_returns_200_with_tol_response | 200 + TOL 표준 응답 |
| test_response_contains_summary_data | summary 데이터 포함 |
| test_provider_called_with_messages | 메시지 전달 확인 |
| test_provider_called_with_summary_context | 이전 요약 컨텍스트 전달 |
| test_system_prompt_contains_token_count | 시스템 프롬프트에 토큰 수 포함 |
| test_response_has_trace_id_header | 응답에 Trace-ID 헤더 |
| test_request_trace_id_echoed_in_response | 요청 Trace-ID 응답에 반환 |

#### TestSummaryEndpointValidation (10개)
| 테스트 | 설명 |
|--------|------|
| test_missing_history_returns_422 | history 누락 → 422 |
| test_empty_history_returns_422 | 빈 history → 422 |
| test_no_body_returns_422 | body 없음 → 422 |
| test_empty_role_returns_422 | 빈 role → 422 |
| test_empty_content_returns_422 | 빈 content → 422 |
| test_invalid_role_returns_422 | 유효하지 않은 role → 422 |
| test_empty_summary_returns_422 | 빈 summary → 422 |
| test_summary_without_history_returns_422 | summary만 전달 → 422 |
| test_summary_optional_succeeds_without_it | summary 없이 성공 |
| test_summary_with_history_succeeds | summary + history 성공 |

#### TestSummaryEndpointScopeValidation (5개)
| 테스트 | 설명 |
|--------|------|
| test_missing_scope_returns_400 | Scope 미전달 → 400 |
| test_disallowed_scope_returns_400 | 비허용 Scope → 400 |
| test_invalid_scope_returns_400 | 유효하지 않은 Scope → 400 |
| test_agent_scope_allowed | agent scope 허용 |
| test_backend_scope_allowed | backend scope 허용 |

#### TestSummaryEndpointGracefulDegradation (1개)
| 테스트 | 설명 |
|--------|------|
| test_provider_failure_returns_503 | 프로바이더 실패 → 503 |

#### TestSummarizeService (4개)
| 테스트 | 설명 |
|--------|------|
| test_summarize_returns_content | 요약 결과 반환 |
| test_summarize_calls_provider_with_primary_role | primary 역할로 호출 |
| test_summarize_passes_trace_metadata | trace metadata 전달 |
| test_summarize_with_previous_summary | 이전 요약 포함 호출 |

---

### 10. test_scoping.py (Scope 필터링)

Scope 필터링 서비스 테스트.

#### TestToolsConfigLoader (7개)
| 테스트 | 설명 |
|--------|------|
| test_load_tools_config_returns_tools_config | ToolsConfig 반환 |
| test_load_tools_config_has_tools | tools 목록 존재 |
| test_tool_config_fields | ToolConfig 필드 확인 |
| test_tool_config_immutable | frozen 확인 |
| test_tool_config_cached | 캐시 동작 |
| test_get_tools_by_scope_filters | scope별 필터링 |
| test_get_tools_by_scope_empty_for_unknown | 없는 scope → 빈 목록 |

#### TestScopingHelpers (1개)
| 테스트 | 설명 |
|--------|------|
| test_get_allowed_scopes | 허용 Scope 목록 조회 |

#### TestGetToolsForScope (6개)
| 테스트 | 설명 |
|--------|------|
| test_valid_scope_returns_tools | 유효 scope → 도구 반환 |
| test_backend_scope_returns_tools | backend scope 도구 반환 |
| test_frontend_scope_returns_list | frontend scope 목록 반환 |
| test_none_scope_raises_error | None scope → 에러 |
| test_invalid_scope_raises_error | 유효하지 않은 scope → 에러 |
| test_filtered_tools_match_scope | 필터 결과 scope 일치 |

#### TestInvalidScopeError (2개)
| 테스트 | 설명 |
|--------|------|
| test_exception_attributes | 예외 속성 확인 |
| test_exception_default_allowed_scopes | 기본 allowed_scopes |

#### TestInvalidScopeHandler (1개)
| 테스트 | 설명 |
|--------|------|
| test_handler_returns_400 | HTTP 400 응답 |

---

### 11. test_tools_endpoint.py (Tools API)

GET /v1/tools 라우터 테스트.

#### TestToolsEndpointSuccess (3개)
| 테스트 | 설명 |
|--------|------|
| test_agent_scope_returns_200 | agent scope → 200 |
| test_backend_scope_returns_200 | backend scope → 200 |
| test_frontend_scope_returns_empty_tools | frontend scope → 빈 도구 목록 |

#### TestOpenAISpec (3개)
| 테스트 | 설명 |
|--------|------|
| test_tool_has_type_function | type=function 확인 |
| test_tool_has_function_fields | name/description/parameters 존재 |
| test_parameters_has_json_schema_structure | JSON Schema 구조 확인 |

#### TestTOLResponseFormat (3개)
| 테스트 | 설명 |
|--------|------|
| test_success_response_has_code_msg_data | code, msg, data 필드 |
| test_success_code_is_tol010100 | TOL010100 코드 확인 |
| test_data_contains_tools_list | data.tools 리스트 확인 |

#### TestToolsEndpointErrors (3개)
| 테스트 | 설명 |
|--------|------|
| test_missing_header_returns_400 | 헤더 미전달 → 400 |
| test_invalid_scope_returns_400 | 유효하지 않은 Scope → 400 |
| test_error_response_has_code_msg_data | 에러 응답 필드 확인 |

#### TestScopeFiltering (3개)
| 테스트 | 설명 |
|--------|------|
| test_agent_tools_contain_summary | agent → summary 도구 포함 |
| test_backend_tools_contain_summary | backend → summary 도구 포함 |
| test_frontend_tools_exclude_summary | frontend → summary 도구 미포함 |

---

### 12. test_proxy_service.py (프록시 서비스)

외부 API 프록시 서비스 테스트.

#### TestProxyConfigLoader (8개)
| 테스트 | 설명 |
|--------|------|
| test_load_returns_proxy_config | ProxyConfig 반환 |
| test_defaults_loaded | defaults 로드 |
| test_targets_loaded | targets 로드 |
| test_target_has_required_fields | 필수 필드 존재 |
| test_get_target_by_name | 이름으로 target 조회 |
| test_get_target_nonexistent_returns_none | 없는 target → None |
| test_get_target_names | target 이름 목록 |
| test_frozen_dataclass | frozen 확인 |

#### TestGetProxyTarget (2개)
| 테스트 | 설명 |
|--------|------|
| test_valid_name_returns_target | 유효 이름 → target 반환 |
| test_invalid_name_raises_error | 유효하지 않은 이름 → 에러 |

#### TestProxyRequest (9개)
| 테스트 | 설명 |
|--------|------|
| test_successful_get_request | GET 요청 성공 |
| test_successful_post_request | POST 요청 성공 |
| test_path_appended_to_base_url | path 추가 확인 |
| test_4xx_error_no_retry | 4xx → 재시도 없음 |
| test_5xx_error_retries | 5xx → 재시도 |
| test_timeout_retries | 타임아웃 → 재시도 |
| test_connection_error_retries | 연결 에러 → 재시도 |
| test_nonexistent_api_raises_error | 없는 API → 에러 |
| test_text_response_body | 텍스트 응답 body 처리 |

#### TestProxyRequestLangfuse (2개)
| 테스트 | 설명 |
|--------|------|
| test_span_created_on_success | 성공 시 span 생성 |
| test_span_records_error_on_failure | 실패 시 span 에러 기록 |

#### TestExternalAPIError (4개)
| 테스트 | 설명 |
|--------|------|
| test_exception_attributes | 예외 속성 확인 |
| test_exception_string | 문자열 표현 |
| test_error_code_exists | 에러 코드 존재 |
| test_error_message_exists | 에러 메시지 존재 |

#### TestExternalAPIErrorHandler (2개)
| 테스트 | 설명 |
|--------|------|
| test_handler_registered | 핸들러 등록 확인 |
| test_handler_returns_502_with_tol_response | HTTP 502 + TOL 응답 |

---

### 13. test_catch_all_handler.py (catch-all 핸들러)

catch-all 예외 핸들러 테스트.

| 테스트 | 설명 |
|--------|------|
| test_unhandled_exception_returns_tol_standard_response | TOL000030 + HTTP 500 응답 |
| test_unhandled_exception_does_not_expose_stacktrace | 스택트레이스 미노출 |
