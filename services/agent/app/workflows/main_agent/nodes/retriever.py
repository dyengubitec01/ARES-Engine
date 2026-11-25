"""
Retriever 노드 - RAG 문서 검색.

Story 2.5: RAG Client를 호출하여 관련 문서를 검색하고 컨텍스트에 저장.
Story 2.8: RunnableConfig 추가, trace_id 전달.

standalone_query를 사용하여 RAG 서버에서 관련 문서를 검색한다.
"""

import structlog
from langchain_core.runnables import RunnableConfig

from app.clients import (
    format_documents_for_context,
    format_documents_to_sources,
    get_rag_client,
)
from app.core.config import settings
from app.core.exceptions import BusinessException
from app.workflows.main_agent.state import AgentState
from app.workflows.shared.tracing_utils import extract_trace_context

logger = structlog.get_logger()


async def retriever(state: AgentState, config: RunnableConfig) -> dict:
    """
    문서 검색 노드.

    RAGClient를 사용하여 standalone_query에 대한 관련 문서를 검색하고,
    포맷팅된 결과를 state.context에 저장한다.

    AC 2.5.1: RAGClient 호출하여 관련 문서 검색
    AC 2.5.3: standalone_query로 검색, format_documents_for_context 사용

    Args:
        state: 현재 워크플로우 상태.

    Returns:
        업데이트할 상태 필드:
        - context: 포맷팅된 문서 목록
        - retrieval_status: 검색 상태 ("skipped" | "ok" | "empty" | "error")
        - thoughts: 추론 과정 추가
    """
    standalone_query = state.get("standalone_query") or state["query"]
    trace_ctx = extract_trace_context(config)

    # SKIP_RAG 플래그가 True면 RAG 검색 건너뛰기
    if settings.SKIP_RAG:
        logger.info("node_skipped", node="retriever", reason="SKIP_RAG=true")
        return {
            "context": [],
            "sources": [],
            "retrieval_status": "skipped",
            "thoughts": ["RAG 검색을 건너뛰었습니다."],
        }

    try:
        rag_client = get_rag_client()
        documents = await rag_client.search(
            query=standalone_query,
            trace_id=trace_ctx.trace_id,
            observation_id=trace_ctx.observation_id,
            user_depts=state.get("user_depts"),
            excluded_docs=state.get("excluded_docs"),
        )

        if documents:
            context = format_documents_for_context(documents)
            sources = format_documents_to_sources(documents)  # Story 2.7
            retrieval_status = "ok"
            thought = f"관련 문서 {len(documents)}건을 검색했습니다."
            logger.info(
                "retriever_completed",
                results_count=len(documents),
                query_preview=standalone_query[:100],
            )
        else:
            context = []
            sources = []
            retrieval_status = "empty"
            thought = "관련 문서를 찾지 못했습니다."
            logger.info("retriever_no_results", query_preview=standalone_query[:100])

    except BusinessException as e:
        # RAG 클라이언트 비즈니스 오류 (워크플로우 계속 진행)
        logger.warning("retriever_rag_call_failed", error=str(e))
        context = []
        sources = []
        retrieval_status = "error"
        thought = "문서 검색 중 오류가 발생했습니다."

    except Exception as e:
        # 예상치 못한 오류도 graceful하게 처리
        logger.error("retriever_unexpected_error", error=str(e), exc_info=True)
        context = []
        sources = []
        retrieval_status = "error"
        thought = "문서 검색 중 오류가 발생했습니다."

    return {
        "context": context,
        "sources": sources,  # Story 2.7: 출처 정보 저장
        "retrieval_status": retrieval_status,
        "thoughts": [thought],
    }
