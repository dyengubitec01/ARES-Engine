# 모델 설정 변경 가이드

## 개요

TOL 서버는 **Role-Based 모델 매핑** 방식을 사용한다. 코드에 모델명이 없고, `config/models.yaml`만 수정하면 모델을 교체할 수 있다.

## 구조

```yaml
# config/models.yaml
roles:
  primary:
    model: "chat-gpt-oss-20b"        # 실제 모델명
    description: "기본 모델"
    fallback_role: "fast"             # 실패 시 전환할 역할
  fast:
    model: "chat-gpt-oss-20b"
    description: "빠른 응답용"
    fallback_role: null               # 체인 종료

default_role: "primary"
fallback_message: "현재 AI 서비스를 이용할 수 없습니다..."
```

## 모델 교체

모델을 바꾸려면 `model` 필드만 수정:

```yaml
roles:
  primary:
    model: "gpt-4o-mini"             # 변경
    fallback_role: "fast"
```

서버 재시작 필요 (`@lru_cache`로 설정 캐싱).

## 새 역할 추가

1. `models.yaml`에 역할 정의:

```yaml
roles:
  primary:
    model: "gpt-4o"
    fallback_role: "fast"
  fast:
    model: "gpt-4o-mini"
    fallback_role: "cheap"            # 새 역할로 연결
  cheap:                              # 새 역할
    model: "gpt-3.5-turbo"
    fallback_role: null
```

2. 코드에서 역할명으로 호출 (변경 불필요):

```python
await provider.invoke_with_failover(role="primary", messages=messages)
# primary 실패 → fast 시도 → cheap 시도 → LLMProviderError
```

## Fallback 체인

`fallback_role`을 따라 체인이 구성된다:

```
primary → fast → null (체인 종료)
```

- 체인 내 모든 역할이 실패하면 `LLMProviderError` 발생 → HTTP 503
- `fallback_message`가 에러 응답의 detail로 사용됨
- 4xx 에러 (429 제외)는 failover 없이 즉시 전파

## Failover 대상

| 에러 유형 | Failover |
|----------|----------|
| 5xx | O (다음 역할로 전환) |
| 429 (Rate Limit) | O |
| Timeout | O |
| Connection Error | O |
| 4xx (429 제외) | X (즉시 전파) |

## 관련 파일

| 파일 | 역할 |
|------|------|
| `config/models.yaml` | 모델 매핑 정의 |
| `src/config/models.py` | YAML 파서 (`dataclass` + `@lru_cache`) |
| `src/providers/gateway.py` | `invoke_with_failover()` — 체인 순회 |
| `tests/test_models.py` | 모델 매핑 테스트 (22건) |
| `tests/test_provider.py` | failover 테스트 (36건) |
