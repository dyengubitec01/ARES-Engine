"""
Query Rewriter 프롬프트 템플릿.

Story 2.2 AC 2.2.2: ChatPromptTemplate 형태로 정의.
Story 3.2.2 AC 3.2.2.1~3: 후속 질문 대명사 해소, 새 주제 분리, few-shot 추가.
Story 3.4: LangFuse Prompt Management 연동 — prompt_manager를 통해 fetch.

대화 이력을 분석하여 모호한 질문을 명확하게 재구성하는 프롬프트.
"""

from langchain_core.prompts import ChatPromptTemplate

# 하드코딩 fallback (3순위)
_FALLBACK_MESSAGES: list[tuple[str, str]] = [
    (
        "system",
        """당신은 사용자의 질문을 벡터 검색(Vector Search)에 최적화된 '독립적 질문'으로 변환하는 전문가입니다.

## 핵심 임무
사용자의 현재 질문이 이전 맥락에 의존하고 있다면, 검색 엔진이 정확한 문서(Embedding)를 찾을 수 있도록 **생략된 주어나 목적어를 반드시 포함**하여 재구성하세요.

## 가이드라인
1. **의미 보존**: 질문의 의도를 바꾸지 마세요. 검색에 필요한 '핵심 명사'를 추가하는 것이 목적입니다.
2. **최소 수정 원칙**: 대명사(그거, 거기 등)가 없거나 이미 충분히 구체적인 질문은 **절대 수정하지 말고 원본 그대로** 반환하세요.
3. **단어 추가 금지**: 원본 질문에 없는 단어나 키워드를 임의로 추가하지 마세요. 대명사를 이전 대화의 구체적 명사로 대체하는 것만 허용됩니다. 유의어, 관련어, 설명 키워드 등을 창작하여 추가하는 것은 금지입니다.
4. **새 주제 격리**: 현재 질문이 이전 대화와 관계없는 새로운 주제라면, 이전 맥락의 키워드를 절대 섞지 마세요.
5. **원문 구조 보존**: 원본 질문의 문장 구조와 어순을 최대한 유지하세요. 대명사를 명사로 대체하더라도 문장을 재구성하거나 어순을 바꾸지 마세요.

## 출력 규칙
- 오직 재구성된 질문만 출력하세요. (설명 금지)""",
    ),
    (
        "user",
        """### 대화 이력:
{history}

### 현재 질문:
{query}

### 재구성된 질문:""",
    ),
]


def get_rewriter_prompt() -> ChatPromptTemplate:
    """Rewriter 프롬프트를 반환한다.

    LangFuse → fallback JSON → 하드코딩 순으로 소싱.
    """
    from app.core.prompt_manager import prompt_manager

    return prompt_manager.get_prompt(
        "rewriter",
        fallback_messages=_FALLBACK_MESSAGES,
    )


# 하위 호환: 기존 import 유지
# 모듈 로드 시점에는 하드코딩 fallback 사용 (테스트 등에서 직접 참조 시)
REWRITER_PROMPT = ChatPromptTemplate.from_messages(_FALLBACK_MESSAGES)
