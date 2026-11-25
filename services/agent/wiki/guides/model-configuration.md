# LLM 모델 설정 가이드

## 개요

Agent Server는 **역할(Role) 기반 모델 라우팅**을 사용합니다. 코드에서 모델명을 직접 쓰지 않고, 역할명(`primary`, `fast`, `reasoning` 등)으로 호출하면 설정 파일에서 실제 모델을 매핑합니다.

## 설정 파일 구조

설정 파일은 `config/` 디렉토리에 있습니다:

- `config/models.yaml` — 운영 환경 (GPU 서버 모델)
- `config/models.test.yaml` — 로컬 테스트 (Ollama 모델)

환경변수 `MODEL_CONFIG_PATH`로 어떤 파일을 사용할지 결정합니다.

```bash
# .env
MODEL_CONFIG_PATH=config/models.yaml       # 운영
MODEL_CONFIG_PATH=config/models.test.yaml   # 로컬 테스트
```

## YAML 구조

```yaml
roles:
  primary:                          # 역할명 (코드에서 이 이름으로 호출)
    model: "chat-gemma-27b"         # 실제 모델명 (LLM 서버에 등록된 이름)
    server: "primary"               # 어느 서버를 사용할지
    fallback_role: "fallback"       # 이 모델 실패 시 대체할 역할
    description: "메인 비즈니스 로직"

servers:
  primary:
    base_url_env: "PRIMARY_LLM_BASE_URL"    # 환경변수에서 URL을 가져옴
  secondary:
    base_url_env: "SECONDARY_LLM_BASE_URL"

fallback_message: "서비스가 일시적으로 불안정합니다."
```

## 모델 변경 방법

### 1. 기존 역할의 모델 교체

예: `primary` 역할의 모델을 `chat-gemma-27b` → `chat-llama-70b`로 변경

```yaml
roles:
  primary:
    model: "chat-llama-70b"   # 여기만 변경
    server: "primary"
    fallback_role: "fallback"
    description: "메인 비즈니스 로직"
```

서버 재시작만 하면 적용됩니다. 코드 변경 없음.

### 2. 새 역할 추가

예: `coding` 역할 추가

```yaml
roles:
  # ... 기존 역할들 ...

  coding:
    model: "deepseek-coder-33b"
    server: "primary"
    fallback_role: "primary"    # 실패 시 primary로 대체
    description: "코드 생성 및 분석"
```

코드에서 사용:

```python
from app.core.llm_factory import llm_factory

llm = llm_factory.get_llm("coding")
response = await llm.ainvoke("이 코드를 리팩토링해줘...")
```

### 3. Fallback 체인 설정

모델 장애 시 자동으로 대체 역할을 사용합니다:

```
primary (chat-gemma-27b)
  └─ 실패 → fallback (chat-gpt-oss-20b, secondary 서버)
              └─ 실패 → fallback_message 반환
```

`fallback_role: null`이면 체인 종료 → `fallback_message` 반환.

### 4. 서버 추가

새 LLM 서버를 추가하려면:

```yaml
servers:
  primary:
    base_url_env: "PRIMARY_LLM_BASE_URL"
  secondary:
    base_url_env: "SECONDARY_LLM_BASE_URL"
  gpu3:                                        # 새 서버
    base_url_env: "TERTIARY_LLM_BASE_URL"      # 새 환경변수
```

`.env`에 해당 환경변수 추가:

```bash
TERTIARY_LLM_BASE_URL=http://gpu3-server:4000/v1
```

`app/core/config.py`의 `Settings` 클래스에도 필드 추가 필요:

```python
TERTIARY_LLM_BASE_URL: str = "http://localhost:4002/v1"
```

## 현재 역할 구성

### 운영 (`config/models.yaml`)

| 역할 | 모델 | 서버 | Fallback | 용도 |
|------|------|------|----------|------|
| primary | chat-gemma-27b | primary | fallback | 메인 비즈니스 로직 |
| fallback | chat-gpt-oss-20b | secondary | — | 장애 시 비상 대응 |
| fast | chat-llama-8b | primary | primary | 단순 요약, 분류, 키워드 추출 |
| reasoning | chat-deepseek-r1-14b | primary | primary | 복잡한 추론 |
| auxiliary | chat-glm4-9b | primary | fast | 다국어 처리 |

### 로컬 테스트 (`config/models.test.yaml`)

| 역할 | 모델 | 서버 | 용도 |
|------|------|------|------|
| primary | qwen2.5:7b | primary | 메인 |
| fallback | qwen2.5:3b | primary | 비상 대응 |
| fast | qwen2.5:3b | primary | 경량 작업 |
| reasoning | qwen2.5:7b | primary | 추론 |
| auxiliary | qwen2.5:3b | primary | 보조 |

## 노드별 사용 역할

| 노드 | 사용 역할 | 이유 |
|------|----------|------|
| rewriter | `primary` | 초기에는 `fast`를 썼으나 재구성 품질이 부족해 `primary`로 변경 |
| router | `fast` | 의도 분류는 단순 작업 |
| synthesizer | `primary` | 최종 답변 생성은 고품질 모델 필요 |

`retriever`와 `tool_executor`는 LLM을 호출하지 않는다.

역할은 코드에 하드코딩되어 있다. 변경 시 아래 위치를 수정한다.

| 노드 | 위치 |
|------|------|
| rewriter | `app/workflows/main_agent/nodes/rewriter.py` — `invoke_chain_with_failover(role=...)` |
| router | `app/workflows/main_agent/nodes/router.py` — `invoke_chain_with_failover(role=...)` |
| synthesizer | `app/workflows/main_agent/nodes/synthesizer.py` — `llm_factory.get_llm(...)` |
