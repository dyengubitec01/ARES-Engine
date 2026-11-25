# 새 도구 추가 가이드

## 개요

TOL 서버에 새 도구를 추가하는 절차. `tools.yaml`에 정의하면 `GET /v1/tools`에 자동 노출되고, `ScopeMiddleware`가 자동으로 Scope 검증을 적용한다.

## 단계

### 1. tools.yaml에 도구 정의

```yaml
# config/tools.yaml
tools:
  - name: "summary"
    endpoint: "/v1/summary"
    description: "텍스트 요약"
    scopes: ["agent", "backend"]
    parameters:
      type: "object"
      properties:
        text:
          type: "string"
          description: "요약할 텍스트"
      required: ["text"]

  - name: "translate"                    # 새 도구
    endpoint: "/v1/translate"
    description: "텍스트 번역"
    scopes: ["agent", "backend"]
    parameters:
      type: "object"
      properties:
        text:
          type: "string"
          description: "번역할 텍스트"
        target_lang:
          type: "string"
          description: "대상 언어 코드"
      required: ["text", "target_lang"]
```

- `endpoint`: 라우터 경로와 일치해야 ScopeMiddleware가 검증
- `scopes`: 이 도구에 접근 가능한 Scope 목록
- `parameters`: OpenAI Function Calling Spec 형식

### 2. 스키마 정의

```python
# src/schemas/translate.py
from pydantic import BaseModel, Field

class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    target_lang: str = Field(..., min_length=2, max_length=5)

class TranslateData(BaseModel):
    translated: str
```

`src/schemas/__init__.py`에 re-export 추가.

### 3. 서비스 구현

```python
# src/services/translate.py
from src.providers.base import BaseLLMProvider

async def translate(
    text: str,
    target_lang: str,
    provider: BaseLLMProvider,
    *,
    trace_context: dict[str, str] | None = None,
) -> str:
    messages = [
        {"role": "system", "content": f"Translate to {target_lang}."},
        {"role": "user", "content": text},
    ]
    response = await provider.invoke_with_failover(
        role="primary",
        messages=messages,
        trace_context=trace_context,
    )
    return response["choices"][0]["message"]["content"]
```

`src/services/__init__.py`에 re-export 추가.

### 4. 라우터 등록

```python
# src/routers/translate.py
from fastapi import APIRouter, Depends, Header, Request
from src.providers.base import BaseLLMProvider
from src.providers.deps import get_llm_provider
from src.schemas.codes import TOLCode
from src.schemas.response import TOLResponse

router = APIRouter(tags=["translate"])

@router.post("/v1/translate", response_model=TOLResponse[TranslateData])
async def translate_endpoint(
    body: TranslateRequest,
    raw_request: Request,
    x_tol_scope: str | None = Header(default=None, alias="X-TOL-Scope"),
    provider: BaseLLMProvider = Depends(get_llm_provider),
) -> TOLResponse[TranslateData]:
    trace_context = getattr(raw_request.state, "trace_context", None)
    result = await translate(
        body.text, body.target_lang, provider,
        trace_context=trace_context,
    )
    return TOLResponse.success(
        code=TOLCode.SUCCESS_QUERY,
        data=TranslateData(translated=result),
    )
```

### 5. main.py에 라우터 등록

```python
# src/main.py
from src.routers.translate import router as translate_router
app.include_router(translate_router)
```

### 6. 테스트 작성

`tests/test_translate_endpoint.py` 생성. 패턴은 `test_summary_endpoint.py` 참조.

## 자동으로 적용되는 것

tools.yaml에 `endpoint` 필드를 정의하면:

- **ScopeMiddleware**: 해당 경로에 대한 `X-TOL-Scope` 검증 자동 적용
- **GET /v1/tools**: 도구 목록에 자동 노출 (OpenAI Function Calling Spec)
- **Langfuse Tracing**: `trace_context` 전달 시 cross-service trace 자동 연결

## 체크리스트

- [ ] `config/tools.yaml`에 도구 정의
- [ ] `src/schemas/` 요청/응답 스키마
- [ ] `src/services/` 비즈니스 로직
- [ ] `src/routers/` 엔드포인트
- [ ] `src/main.py` 라우터 등록
- [ ] `__init__.py` re-export 추가 (schemas, services, routers)
- [ ] 테스트 작성
- [ ] `trace_context` 전파 (cross-service tracing)

## 관련 파일

| 파일 | 역할 |
|------|------|
| `config/tools.yaml` | 도구 정의 + Scope 매핑 |
| `src/config/tools.py` | YAML 파서 |
| `src/middleware/scope.py` | ScopeMiddleware (자동 Scope 검증) |
| `src/routers/tools.py` | GET /v1/tools (자동 노출) |
