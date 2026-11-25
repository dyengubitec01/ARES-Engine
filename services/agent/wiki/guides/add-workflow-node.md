# 워크플로우 노드 추가 가이드

## 개요

Agent Server의 워크플로우는 [LangGraph](https://langchain-ai.github.io/langgraph/)로 구성되어 있습니다. 새 노드를 추가하려면 **3개 파일**을 수정합니다:

1. `app/workflows/main_agent/nodes/` — 노드 함수 생성
2. `app/workflows/main_agent/graph.py` — 그래프에 노드와 엣지 등록
3. `app/workflows/main_agent/state.py` — 필요 시 상태 필드 추가

## 현재 그래프 구조

```
START → rewriter → router ─┬─ (rag)    → retriever ──────────────→ synthesizer → END
                            ├─ (tool)   → tool_executor ──────────→ synthesizer → END
                            ├─ (both)   → retriever ∥ tool_executor → synthesizer → END
                            └─ (direct) ────────────────────────────→ synthesizer → END
```

`direct`는 `SKIP_DIRECT` 기본값이 `true`라 평소에는 비활성입니다. 자세한 내용은 [라우터 테스트 가이드](router-testing.md)를 참조하세요.

## 단계별 가이드

### Step 1: 노드 함수 생성

`app/workflows/main_agent/nodes/` 디렉토리에 새 파일을 생성합니다.

**예시: `validator.py` (답변 검증 노드)**

```python
"""Validator 노드 — Synthesizer 출력을 검증한다."""

import structlog

from app.core.exceptions import BusinessException
from app.core.llm_factory import llm_factory
from app.workflows.main_agent.prompts.validator import get_validator_prompt
from app.workflows.main_agent.state import AgentState

logger = structlog.get_logger()


async def validator(state: AgentState) -> dict:
    """Synthesizer의 응답을 검증하고 필요 시 수정한다.

    Args:
        state: 현재 워크플로우 상태.

    Returns:
        업데이트할 상태 필드 dict.
    """
    response = state.get("response", "")
    query = state["query"]
    session_id = state["session_id"]

    try:
        # chain 패턴 — failover + LangFuse Prompt-Generation 연결이 자동으로 붙는다
        result = await llm_factory.invoke_chain_with_failover(
            role="fast",
            prompt=get_validator_prompt(),
            input_dict={"query": query, "response": response},
            session_id=session_id,
            request_type="answer_validation",
        )
        content = result.content if isinstance(result.content, str) else ""
        is_valid = "적절" in content
        logger.info("validator_completed", is_valid=is_valid)

    except BusinessException as e:
        # LLM 실패 시 원본 응답을 유지하고 워크플로우는 계속 진행한다
        logger.warning("validator_llm_failed", error=str(e))
        return {"thoughts": ["검증을 건너뛰었습니다."]}

    return {
        "response": response if is_valid else content,
        "thoughts": [f"검증 결과: {'통과' if is_valid else '수정됨'}"],
    }
```

**핵심 규칙:**
- 함수 시그니처: `async def node_name(state: AgentState) -> dict`
- 반환값: 업데이트할 상태 필드만 포함하는 dict
- `thoughts` 필드는 `Annotated[list, operator.add]` 리듀서로 자동 누적됨
- **LLM 호출은 반드시 `llm_factory.invoke_chain_with_failover()`를 경유한다.** `get_llm().ainvoke()`를 직접 부르면 서버 장애 시 fallback role로 넘어가지 못하고, LangFuse의 Prompt ↔ Generation 연결도 끊긴다. 토큰 단위 스트리밍이 필요한 경우에만 `get_llm()` + `astream`을 쓴다 (현재 `synthesizer`가 유일한 예외)
- **LLM 실패는 `BusinessException`으로 잡아 graceful degradation한다.** 노드 하나가 죽어서 전체 스트림이 끊기지 않도록, 기존 `rewriter` / `router` / `retriever` 모두 실패 시 기본값으로 진행한다
- **로거는 `structlog.get_logger()`를 쓰고 `event_name` + 키-값으로 기록한다** (ADR-004). f-string 메시지는 금지 — `logger.info(f"...")` 대신 `logger.info("event_name", key=value)`

### Step 2: `__init__.py`에 export 추가

`app/workflows/main_agent/nodes/__init__.py`:

```python
from app.workflows.main_agent.nodes.validator import validator  # 추가
```

### Step 3: 그래프에 등록

`app/workflows/main_agent/graph.py`를 수정합니다.

```python
from app.workflows.main_agent.nodes import (
    retriever,
    rewriter,
    router,
    synthesizer,
    tool_executor,
    validator,        # 추가
)

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # 기존 노드들
    graph.add_node("rewriter", rewriter)
    graph.add_node("router", router)
    graph.add_node("retriever", retriever)
    graph.add_node("tool_executor", tool_executor)
    graph.add_node("synthesizer", synthesizer)
    graph.add_node("validator", validator)     # 추가

    # 엣지 수정: synthesizer → validator → END
    graph.add_edge(START, "rewriter")
    graph.add_edge("rewriter", "router")
    graph.add_conditional_edges("router", route_by_intent, {
        "rag": "retriever",
        "tool": "tool_executor",
        "direct": "synthesizer",
    })
    graph.add_edge("retriever", "synthesizer")
    graph.add_edge("tool_executor", "synthesizer")
    graph.add_edge("synthesizer", "validator")   # 변경: synthesizer → validator
    graph.add_edge("validator", END)             # 변경: validator → END

    return graph
```

### Step 4: 상태 필드 추가 (필요 시)

새 노드가 기존 상태 필드로 충분하면 이 단계는 생략합니다.

새 필드가 필요하면 `app/workflows/main_agent/state.py`를 수정합니다:

```python
class AgentState(TypedDict):
    # 기존 필드들 ...
    query: str
    session_id: str
    response: str
    thoughts: Annotated[list[str], operator.add]
    context: Annotated[list[str], operator.add]

    # 새 필드 추가
    validation_score: float    # 검증 점수
```

**리듀서 패턴:** 여러 노드가 같은 필드에 값을 추가해야 하면 `Annotated[list, operator.add]`를 사용합니다. fan-out(병렬 실행) 시 자동으로 리스트가 병합됩니다.

## 프롬프트 템플릿 추가

노드가 LLM을 호출하면 프롬프트가 필요합니다. 프롬프트는 LangFuse에서 관리하고, 코드에는 하드코딩 fallback만 둡니다. 자세한 fallback 체인은 [README 6.4](../../README.md#64-프롬프트-관리-langfuse)를 참조하세요.

### 1) 프롬프트 모듈 생성

```python
# app/workflows/main_agent/prompts/validator.py

from langchain_core.prompts import ChatPromptTemplate

# 하드코딩 fallback (3순위)
_FALLBACK_MESSAGES: list[tuple[str, str]] = [
    ("system", "당신은 답변 검증 전문가입니다. ..."),
    ("user", "질문: {query}\n답변: {response}\n\n검증 결과를 알려주세요."),
]


def get_validator_prompt() -> ChatPromptTemplate:
    """Validator 프롬프트를 반환한다.

    LangFuse → fallback JSON → 하드코딩 순으로 소싱.
    """
    from app.core.prompt_manager import prompt_manager

    return prompt_manager.get_prompt(
        "validator",
        fallback_messages=_FALLBACK_MESSAGES,
    )
```

### 2) `config/prompts.yaml`에 등록 (필수)

`prompt_manager`는 이 파일에서 프롬프트의 타입과 기대 변수를 읽습니다. **등록하지 않으면 `get_prompt()`가 `KeyError`로 실패**합니다.

```yaml
prompts:
  # 기존 프롬프트들 ...
  validator:
    variables: [query, response]
    type: chat
```

`variables`는 프롬프트 템플릿의 플레이스홀더와 정확히 일치해야 합니다. Jenkins의 `Validate Prompts` 단계가 LangFuse에 등록된 프롬프트의 변수와 이 목록을 대조하며, 불일치하면 배포가 중단됩니다.

### 3) LangFuse에 프롬프트 등록

LangFuse UI에서 `validator`라는 이름으로 `production` 라벨을 붙여 등록합니다. 등록 전까지는 하드코딩 fallback으로 동작합니다.

## 조건부 엣지 추가

분기가 필요하면 `add_conditional_edges`를 사용합니다:

```python
def route_by_validation(state: AgentState) -> str:
    """검증 결과에 따라 다음 노드를 결정한다."""
    score = state.get("validation_score", 1.0)
    if score < 0.5:
        return "synthesizer"  # 재생성
    return "end"

graph.add_conditional_edges("validator", route_by_validation, {
    "synthesizer": "synthesizer",
    "end": END,
})
```

## 테스트 작성

`tests/test_validator.py`를 생성합니다:

```python
import pytest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from app.workflows.main_agent.nodes.validator import validator


class TestValidatorNode:
    @pytest.fixture
    def base_state(self):
        return {
            "query": "테스트 질문",
            "session_id": "test-session",
            "response": "테스트 답변",
            "thoughts": [],
        }

    async def test_validator_returns_thoughts(self, base_state):
        with patch("app.workflows.main_agent.nodes.validator.llm_factory") as mock:
            mock.invoke_chain_with_failover = AsyncMock(
                return_value=AIMessage(content="적절합니다")
            )
            result = await validator(base_state)
            assert "thoughts" in result
            assert len(result["thoughts"]) > 0
```

노드가 `invoke_chain_with_failover`를 쓰므로 목도 그 메서드에 걸어야 합니다. `get_llm`을 목킹하면 실제 호출 경로와 어긋나 테스트가 통과해도 의미가 없습니다.

## 체크리스트

- [ ] `app/workflows/main_agent/nodes/` 에 노드 파일 생성
- [ ] `nodes/__init__.py`에 export 추가
- [ ] `graph.py`에 `add_node` + 엣지 등록
- [ ] `state.py`에 필요한 상태 필드 추가 (해당 시)
- [ ] `prompts/`에 프롬프트 모듈 추가 + `config/prompts.yaml`에 등록 (LLM 호출 시 필수)
- [ ] LangFuse에 프롬프트를 `production` 라벨로 등록
- [ ] LLM 호출이 `invoke_chain_with_failover()`를 경유하는지 확인
- [ ] `tests/`에 단위 테스트 작성
- [ ] 기존 테스트 통과 확인: `uv run pytest`
