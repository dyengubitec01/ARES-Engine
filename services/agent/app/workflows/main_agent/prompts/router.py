"""
Intent Router 프롬프트 템플릿.

Story 2.8 AC 2.8.3: 사용자 질문의 의도를 분석하여 실행 경로를 결정하는 프롬프트.
Story 3.2.2 AC 3.2.2.4~6: 2단계 판단 전략 + 동적 경로 제어.
Story 3.4: LangFuse Prompt Management 연동 — prompt_manager를 통해 fetch.
"""

from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings

# 경로별 설명 텍스트
_ROUTE_DESCRIPTIONS: dict[str, str] = {
    "rag": "- rag: 사내문서, 업무 관련 정보 검색이 필요한 경우",
    "tool": (
        "- tool: 외부 도구 실행이 필요한 경우"
        " (날씨, 계산, API 호출, 실시간 데이터 등)"
    ),
    "both": "- both: 사내문서 검색과 도구 실행 모두 필요한 경우",
    "direct": (
        "- direct: 일반 상식, 시사, 인사, 일반 대화 등"
        " 사내문서 검색이 불필요한 경우"
    ),
}

# 하드코딩 fallback 시스템 프롬프트 (3순위)
# LangChain 변수 문법({변수})으로 통일. routes_text, route_options는 partial()로 주입.
_FALLBACK_SYSTEM_PROMPT = """당신은 사용자 질문의 의도를 분석하여 실행 경로를 결정하는 라우터입니다.

## 사용 가능한 경로
{routes_text}

## 판단 전략 (2단계)

### 1단계: 키워드 매칭 (우선)
다음 키워드가 명시적으로 포함되면 해당 경로로 즉시 결정하세요:
- "사내문서", "규정", "매뉴얼", "문서 검색", "RAG노드사용" → rag
- "날씨", "계산", "API", "실시간", "TOOL노드사용" → tool
- 사내문서 검색 키워드와 도구 키워드가 모두 포함 → both

### 2단계: 의도 분석 (키워드 없을 때)
키워드가 없으면 질문의 의도를 분석하세요:
- 사내·업무·조직 관련 정보 조회 → rag
- 실시간·외부 데이터 필요 → tool
- 일반 상식, 시사, 뉴스, 인사, 일상 대화 → direct

**도메인 힌트:** 다음 키워드가 포함되면 사내 업무 관련 질문일 가능성이 높습니다:
수주, 용역, 정책, 정부, 수립, 군청, 시청, 제안서, 보고서

**원칙:** 확실히 일반 상식/인사/시사인 경우만 direct로 보내세요. 판단이 애매하면 rag로 보내세요.

## 예시
- "사내 휴가 규정 알려줘" → rag (사내 규정)
- "농기계 매뉴얼 찾아줘" → rag (업무 문서)
- "서버 상태 확인해줘" → tool (실시간 데이터)
- "이스라엘-하마스 전쟁 알려줘" → direct (시사/뉴스)
- "파이썬이란 무엇인가요?" → direct (일반 상식)
- "안녕하세요" → direct (인사)
- "3 더하기 5는?" → direct (간단 계산)
- "사내문서에서 찾아서 이메일로 보내줘" → both (검색 + 도구)

## 응답
다음 중 하나만 응답하세요: {route_options}"""


def get_available_routes() -> list[str]:
    """SKIP 플래그를 기반으로 사용 가능한 경로 목록을 반환한다.

    SKIP 매트릭스:
        SKIP_RAG=F, SKIP_TOOL=F, SKIP_DIRECT=F → rag, tool, both, direct
        SKIP_RAG=F, SKIP_TOOL=F, SKIP_DIRECT=T → rag, tool, both
        SKIP_RAG=F, SKIP_TOOL=T, SKIP_DIRECT=T → rag
        SKIP_RAG=T, SKIP_TOOL=F, SKIP_DIRECT=T → tool
    """
    routes = []
    skip_rag = settings.SKIP_RAG
    skip_tool = settings.SKIP_TOOL
    skip_direct = settings.SKIP_DIRECT

    if not skip_direct:
        routes.append("direct")
    if not skip_rag:
        routes.append("rag")
    if not skip_tool:
        routes.append("tool")
    if not skip_rag and not skip_tool:
        routes.append("both")

    return routes


def _build_routes_text(available_routes: list[str]) -> str:
    """경로 설명 텍스트를 생성한다."""
    return "\n".join(
        _ROUTE_DESCRIPTIONS[r]
        for r in available_routes
        if r in _ROUTE_DESCRIPTIONS
    )


def build_router_prompt(available_routes: list[str]) -> ChatPromptTemplate:
    """가용 경로에 맞는 Router 프롬프트를 동적으로 생성한다.

    LangFuse에서 시스템 프롬프트 본문을 가져오고,
    routes_text와 route_options를 코드에서 주입한다.

    Args:
        available_routes: 사용 가능한 경로 목록.

    Returns:
        ChatPromptTemplate.
    """
    routes_text = _build_routes_text(available_routes)
    route_options = ", ".join(available_routes)

    # LangFuse에서 프롬프트 fetch 시도
    try:
        from app.core.prompt_manager import prompt_manager

        lf_prompt = prompt_manager.get_prompt(
            "router",
            fallback_messages=[
                ("system", _FALLBACK_SYSTEM_PROMPT),
                ("user", "{query}"),
            ],
        )
    except Exception:
        # prompt_manager 자체가 실패하면 하드코딩 fallback
        lf_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _FALLBACK_SYSTEM_PROMPT),
                ("user", "{query}"),
            ]
        )

    # routes_text, route_options를 partial()로 주입
    # LangFuse/fallback 모두 동일한 방식으로 처리
    return lf_prompt.partial(
        routes_text=routes_text,
        route_options=route_options,
    )


# 하위 호환: 기존 import 유지 (테스트 등에서 ROUTER_PROMPT 직접 참조 시)
ROUTER_PROMPT = build_router_prompt(get_available_routes())
