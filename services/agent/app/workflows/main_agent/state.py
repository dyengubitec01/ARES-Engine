"""
AgentState - LangGraph 워크플로우 상태 정의.

Story 2.1: LangGraph 기본 워크플로우 구조 설정
모든 노드가 공유하는 상태 스키마를 TypedDict로 정의한다.

Story 2.7: sources 필드 추가 (출처 정보)
Story 2.8: route 필드 추가, State Reducer 도입 (operator.add)
"""

import operator
from typing import Annotated, NotRequired, TypedDict


class Source(TypedDict):
    """출처 정보 스키마 (AC 2.7.6)."""

    doc_id: str
    """문서 고유 식별자."""

    doc_title: str
    """문서 제목."""

    doc_content: str
    """문서 내용."""


class AgentState(TypedDict):
    """
    LangGraph 워크플로우의 공유 상태.

    모든 노드는 이 상태를 받아서 일부 필드만 업데이트하여 반환한다.

    Story 2.8: 리스트 필드에 operator.add reducer를 적용하여
    병렬 실행(fan-out) 시 자동 병합을 지원한다.
    각 노드는 자기 결과만 반환하면 reducer가 기존 값에 append한다.
    """

    # === 입력 필드 ===
    query: str
    """사용자의 원본 질문."""

    history: list[dict]
    """대화 이력. 각 항목은 {'role': str, 'content': str} 형태."""

    session_id: str
    """세션 식별자. LangFuse 트레이싱 및 대화 추적에 사용."""

    # === 처리 중 필드 (Reducer 적용) ===
    standalone_query: NotRequired[str]
    """문맥을 반영한 독립적 질문. RAG 검색에 사용된다."""

    context: Annotated[list[str], operator.add]
    """RAG/Tool에서 검색된 문서 또는 정보 목록. reducer: 자동 병합."""

    # === 출력 필드 ===
    response: NotRequired[str]
    """최종 생성된 답변."""

    thoughts: Annotated[list[str], operator.add]
    """
    Chain of Thought - 각 노드의 추론 과정. reducer: 자동 병합.
    각 노드는 자기 thought만 반환하면 자동으로 누적된다.
    """

    # === 출처 정보 필드 (Story 2.7) ===
    sources: Annotated[list[Source], operator.add]
    """RAG 검색 결과 출처 정보. done 이벤트에 포함. reducer: 자동 병합."""

    # === 라우팅 필드 (Story 2.8) ===
    route: NotRequired[str]
    """라우터 결정 경로. "rag" | "tool" | "both" | "direct" """

    retrieval_status: NotRequired[str]
    """RAG 검색 상태. "skipped" | "ok" | "empty" | "error" — retriever 노드만 기록(단일 작성자)."""

    # === 사용자 정보 필드 ===
    user_depts: list[str]
    """사용자 부서 ID 목록. RAG 검색 시 전달."""

    excluded_docs: list[str]
    """제외할 문서 content-id 목록. RAG 검색 시 전달."""

    # === 메타데이터 필드 ===
    retry_count: NotRequired[int]
    """재시도 횟수. Grader 실패 또는 에러 발생 시 증가."""

    error: NotRequired[str | None]
    """에러 메시지. 예외 발생 시 저장되며, 정상 시 None."""


def create_initial_state(
    query: str,
    session_id: str,
    history: list[dict] | None = None,
    user_depts: list[str] | None = None,
    excluded_docs: list[str] | None = None,
) -> AgentState:
    """
    초기 AgentState를 생성한다.

    Args:
        query: 사용자의 질문.
        session_id: 세션 식별자.
        history: 대화 이력 (기본값: 빈 리스트).
        user_depts: 사용자 부서 ID 목록.
        excluded_docs: 제외할 문서 content-id 목록.

    Returns:
        초기화된 AgentState.
    """
    return AgentState(
        query=query,
        history=history or [],
        session_id=session_id,
        standalone_query="",
        context=[],
        response="",
        thoughts=[],
        sources=[],
        route="",
        retrieval_status="skipped",
        retry_count=0,
        error=None,
        user_depts=user_depts or [],
        excluded_docs=excluded_docs or [],
    )
