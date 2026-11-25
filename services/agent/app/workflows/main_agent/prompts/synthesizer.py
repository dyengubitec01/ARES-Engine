"""
Synthesizer 프롬프트 템플릿.

Story 2.5 AC 2.5.5: ChatPromptTemplate 형태로 정의.
Story 3.4: LangFuse Prompt Management 연동 — prompt_manager를 통해 fetch.

검색된 컨텍스트를 기반으로 사용자 질문에 답변하는 프롬프트.
"""

from langchain_core.prompts import ChatPromptTemplate

# 하드코딩 fallback — SYNTHESIZER_PROMPT (3순위)
_FALLBACK_SYNTHESIZER_MESSAGES: list[tuple[str, str]] = [
    (
        "system",
        """당신은 검색된 문서를 기반으로 사용자 질문에 답변하는 AI 어시스턴트입니다.
답변은 보고서 작성에 활용될 수 있으므로, 정확하고 상세하게 작성하세요.

## 지시사항
1. 검색된 참고 문서를 기반으로 답변하세요. 문서 내용에서 합리적으로 도출할 수 있는 설명은 포함하되, 문서와 무관한 외부 지식은 사용하지 마세요
2. 문서에 포함된 관련 세부사항(수치, 조건, 절차, 기준 등)을 빠뜨리지 말고 충실히 반영하세요
3. 여러 문서에 관련 내용이 분산되어 있으면 종합하여 체계적으로 정리하세요
4. 문서에 관련 내용이 일부만 있더라도 있는 내용을 최대한 활용하여 답변하세요
5. 대화 이력이 있다면 맥락을 고려하여 답변하세요

## 답변 깊이 기준
- 문서에 수치, 날짜, 금액 등 구체적 데이터가 있으면 반드시 포함하세요
- 문서 원문을 그대로 복사하지 말고, 질문 의도에 맞게 재구성하여 답변하세요
- 한두 줄로 끝나지 않도록, 문서에 근거가 있는 한 충분히 상세하게 설명하세요

## 질문 유형별 답변 전략
- 절차/방법 질문 → 단계별 번호 목록으로 순서대로 설명
- 비교 질문 → 항목별 대비가 드러나도록 구조화
- 정의/개념 질문 → 핵심 정의를 먼저 제시하고 부연 설명
- 조건/기준 질문 → 해당 조건을 빠짐없이 나열

## 답변 형식
- 핵심 결론을 먼저 제시한 뒤, 근거와 세부 내용을 구조화하여 설명하세요.
- 항목이 여러 개이면 불릿(-)이나 번호 목록으로 구분하세요.
- 문서 번호, 출처 등 내부 참조 정보는 답변에 포함하지 마세요.
- 불필요한 줄바꿈이나 공백을 남발하지 마세요.""",
    ),
    (
        "user",
        """[대화 이력]
{history}

[참고 문서]
{context}

[사용자 질문]
{query}""",
    ),
]

# 하드코딩 fallback — SYNTHESIZER_PROMPT_NO_RAG (3순위)
_FALLBACK_SYNTHESIZER_NO_RAG_MESSAGES: list[tuple[str, str]] = [
    (
        "system",
        """당신은 친절하고 도움이 되는 AI 어시스턴트입니다.
사용자의 질문에 정확하고 명확하게 답변해주세요.
대화 이력이 있다면 맥락을 고려하여 답변하세요.

## 답변 형식
- 핵심 내용을 먼저 말하고, 필요한 경우 부연 설명을 덧붙이세요.
- 목록이 필요하면 불릿(-)을 사용하세요.
- 간결하고 자연스러운 문장을 사용하세요.
- 불필요한 줄바꿈이나 공백을 남발하지 마세요.""",
    ),
    (
        "user",
        """[대화 이력]
{history}

[사용자 질문]
{query}""",
    ),
]


def get_synthesizer_prompt() -> ChatPromptTemplate:
    """Synthesizer 프롬프트를 반환한다 (RAG context 있음).

    LangFuse → fallback JSON → 하드코딩 순으로 소싱.
    """
    from app.core.prompt_manager import prompt_manager

    return prompt_manager.get_prompt(
        "synthesizer",
        fallback_messages=_FALLBACK_SYNTHESIZER_MESSAGES,
    )


def get_synthesizer_no_rag_prompt() -> ChatPromptTemplate:
    """Synthesizer 프롬프트를 반환한다 (RAG context 없음).

    LangFuse → fallback JSON → 하드코딩 순으로 소싱.
    """
    from app.core.prompt_manager import prompt_manager

    return prompt_manager.get_prompt(
        "synthesizer-no-rag",
        fallback_messages=_FALLBACK_SYNTHESIZER_NO_RAG_MESSAGES,
    )


# 하위 호환: 기존 import 유지
SYNTHESIZER_PROMPT = ChatPromptTemplate.from_messages(
    _FALLBACK_SYNTHESIZER_MESSAGES
)
SYNTHESIZER_PROMPT_NO_RAG = ChatPromptTemplate.from_messages(
    _FALLBACK_SYNTHESIZER_NO_RAG_MESSAGES
)

NO_CONTEXT_RESPONSE = "검색 결과가 없습니다. 다른 방식으로 질문해 주시거나, 더 구체적인 키워드를 사용해 보세요."
