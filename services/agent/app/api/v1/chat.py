"""
Chat API Endpoint (Story 2.6).

SSE Streaming 기반 실시간 채팅 엔드포인트.
LangGraph astream_events를 통한 노드별 span 자동 추적.

AC 2.6.1: SSE 엔드포인트 (StreamingResponse, text/event-stream)
AC 2.6.2: 이벤트 타입 (thought, message, error, done)
AC 2.6.3: Thought 이벤트 (노드 완료 시 전송)
AC 2.6.4: Message 스트리밍 (Synthesizer 토큰 단위)
AC 2.6.5: Error 이벤트 (BusinessException 기반)
AC 2.6.6: 요청 스키마 (ChatRequest)
AC 2.6.7: Done 이벤트 (스트림 종료)
AC 2.6.8: 클라이언트 연결 해제 처리
AC 2.6.10: LangFuse 스트리밍 output 캡처
AC 2.6.11: LangFuse 노드별 span 추적 (astream_events)
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import structlog
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from app.core.config import settings
from app.core.enums import ErrorCode
from app.core.exceptions import BusinessException
from app.core.tracing import tracing
from app.workflows.main_agent.graph import get_compiled_graph
from app.workflows.main_agent.state import create_initial_state

logger = structlog.get_logger()

router = APIRouter(prefix="/v1", tags=["chat"])


# ============================================================================
# Request/Response Schemas (AC 2.6.6)
# ============================================================================
class ChatRequest(BaseModel):
    """Chat 요청 스키마 (AC 2.7.1)."""

    query: str
    """사용자 질문."""

    session_id: str
    """세션 식별자."""

    summary: str | None = None
    """요약 (선택)."""

    history: list[dict] = []
    """대화 이력. 각 항목은 {"role": str, "content": str} 형태."""

    user_id: str | None = None
    """사용자 식별자 (LangFuse 트레이싱용)."""

    user_position: str | None = None
    """사용자 직급/직책 (추후 활용 예정)."""

    user_depts: list[str]
    """사용자 부서 ID 목록."""

    excluded_docs: list[str] = []
    """제외할 문서 content-id 목록 (선택)."""

    @field_validator("query", "session_id")
    @classmethod
    def validate_not_blank(cls, v: str, info) -> str:
        """필수 필드 공백 검증 (AC 2.7.2)."""
        if not v or not v.strip():
            raise ValueError(f"{info.field_name}은(는) 비어있을 수 없습니다.")
        return v

    @field_validator("user_depts")
    @classmethod
    def validate_user_depts(cls, v: list[str]) -> list[str]:
        """부서 목록 검증 (AC 3.6.2)."""
        if not v:
            raise ValueError("user_depts은(는) 비어있을 수 없습니다.")
        for item in v:
            if not item or not item.strip():
                raise ValueError("user_depts의 각 항목은 비어있을 수 없습니다.")
        return v


# ============================================================================
# SSE Event Formatter (AC 2.6.2)
# ============================================================================
def format_sse(event: str, data: dict[str, Any]) -> str:
    """
    SSE 이벤트 포맷으로 변환.

    Args:
        event: 이벤트 타입 (thought, message, error, done)
        data: 이벤트 데이터

    Returns:
        SSE 포맷 문자열: "event: {type}\\ndata: {json}\\n\\n"
    """
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {json_data}\n\n"


# ============================================================================
# Node Thought Messages
# ============================================================================
NODE_THOUGHTS = {
    "rewriter": "질문을 분석했습니다.",
    "router": "질문 의도를 파악했습니다.",
    "retriever": "관련 문서를 검색했습니다.",
    "tool_executor": "도구를 실행하고 있습니다.",
    "synthesizer": "답변을 생성하고 있습니다...",
}

# 검색 0건/오류 시 답변에 앞서 전송하는 고지 문구 (rag 경로 한정)
RETRIEVAL_NOTICE_EMPTY = "사내 문서에서 관련 내용을 찾지 못해 일반 지식 수준에서 답변드립니다.\n\n"
RETRIEVAL_NOTICE_ERROR = "문서 검색 중 오류가 발생하여 일반 지식 수준에서 답변드립니다.\n\n"


# ============================================================================
# Streaming Workflow with astream_events (AC 2.6.3, 2.6.4, 2.6.11)
# ============================================================================
async def stream_workflow(request: ChatRequest) -> AsyncIterator[str]:
    """
    LangGraph astream_events를 사용한 스트리밍 워크플로우.

    각 노드 실행이 LangFuse에 자동으로 span으로 기록되며,
    노드 완료 시 thought 이벤트, LLM 스트리밍 시 message 이벤트를 전송.
    LLM 호출 완료 시 usage_metadata를 전 노드 합산하여 done 이벤트의
    usage 필드로 전달한다 (AC 6.1.1~6.1.8).
    rag 경로에서 검색이 0건이거나 실패하면 고지 문구를 message 이벤트로
    선전송하고, done 이벤트에 최종 답변 정본(response)을 포함한다.

    Args:
        request: Chat 요청

    Yields:
        SSE 포맷 이벤트 문자열
    """
    # 초기 상태 생성
    initial_state = create_initial_state(
        query=request.query,
        session_id=request.session_id,
        history=request.history,
        user_depts=request.user_depts,
        excluded_docs=request.excluded_docs,
    )

    # LangFuse 트레이싱 설정 (AC 2.6.11)
    config = tracing.get_langfuse_config(
        session_id=request.session_id,
        user_id=request.user_id,
        tags=["chat", "streaming"],
        metadata={
            "query_preview": request.query[:50],
            "history_length": len(request.history),
        },
    )

    graph = get_compiled_graph()
    completed_nodes: set[str] = set()
    sources: list[dict] = []  # Story 2.7: 출처 정보 저장
    route = ""  # router 결정 경로 (고지 전송 조건 판정용)
    sent_notice = ""  # 전송한 고지 문구 (done.response에 합산)
    final_response = ""  # synthesizer 후처리 정본 (done.response)
    partial_chunks: list[str] = []  # 에러 done의 부분 response용 청크 버퍼
    # AC 6.1.1 / 6.1.2: 전 LLM 호출(rewriter/router/synthesizer) usage_metadata 합산
    total_input_tokens = 0
    total_output_tokens = 0
    stream_start = time.perf_counter()

    def _build_usage() -> dict[str, int]:
        """done payload에 실을 usage 객체 (정상/에러 경로 공용, AC 6.1.3)."""
        return {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
        }

    # LangFuse trace_id 추출 (stream_completed 로그용)
    langfuse_trace_id = None
    if config.get("callbacks"):
        for cb in config["callbacks"]:
            if hasattr(cb, "trace_id"):
                langfuse_trace_id = cb.trace_id
                break

    try:
        async for event in graph.astream_events(
            initial_state,
            config=config,
            version="v2",
        ):
            kind = event["event"]
            name = event.get("name", "")

            # 노드 시작 시 thought 이벤트 (AC 2.6.3)
            if kind == "on_chain_start" and name in NODE_THOUGHTS:
                if name not in completed_nodes:
                    completed_nodes.add(name)
                    if settings.INCLUDE_THOUGHTS_IN_RESPONSE:
                        yield format_sse("thought", {"content": NODE_THOUGHTS[name]})

            # router 완료 시 route 캡처 (고지 전송 조건 판정용)
            elif kind == "on_chain_end" and name == "router":
                output = event.get("data", {}).get("output", {})
                if isinstance(output, dict):
                    route = output.get("route", "")

            # retriever 완료 시 sources/검색 상태 캡처 (Story 2.7)
            elif kind == "on_chain_end" and name == "retriever":
                output = event.get("data", {}).get("output", {})
                if isinstance(output, dict):
                    sources = output.get("sources", [])
                    retrieval_status = output.get("retrieval_status", "skipped")
                    # 검색 0건/오류 시 고지 문구를 답변에 앞서 전송
                    if route == "rag" and retrieval_status in ("empty", "error"):
                        sent_notice = (
                            RETRIEVAL_NOTICE_ERROR
                            if retrieval_status == "error"
                            else RETRIEVAL_NOTICE_EMPTY
                        )
                        yield format_sse("message", {"content": sent_notice})

            # synthesizer 완료 시 후처리 정본 캡처 (done.response용)
            elif kind == "on_chain_end" and name == "synthesizer":
                output = event.get("data", {}).get("output", {})
                if isinstance(output, dict):
                    final_response = output.get("response", "")

            # LLM 토큰 스트리밍 시 message 이벤트 (AC 2.6.4)
            # synthesizer 노드의 LLM 청크만 중계 (router/rewriter LLM 응답 노출 방지)
            elif (
                kind == "on_chat_model_stream"
                and "synthesizer" in completed_nodes
                and event.get("metadata", {}).get("langgraph_node") == "synthesizer"
            ):
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    partial_chunks.append(chunk.content)
                    yield format_sse("message", {"content": chunk.content})

            # AC 6.1.1 / 6.1.2: LLM 호출 완료 시 usage_metadata 전 노드 합산
            elif kind == "on_chat_model_end":
                output = event.get("data", {}).get("output")
                um = getattr(output, "usage_metadata", None)
                if um:
                    total_input_tokens += um.get("input_tokens", 0) or 0
                    total_output_tokens += um.get("output_tokens", 0) or 0
                else:
                    # AC 6.1.5: 모델/proxy 설정 이상 조기 감지용 WARN
                    node = event.get("metadata", {}).get("langgraph_node", "unknown")
                    logger.warning(
                        "usage_metadata_missing",
                        langgraph_node=node,
                        event_name=name,
                    )

        # Done 이벤트 (AC 2.7.6, AC 6.1.3) - 성공 시 sources + usage 포함
        yield format_sse(
            "done",
            {
                "code": ErrorCode.SUCCESS.code,
                "msg": ErrorCode.SUCCESS.msg,
                "response": sent_notice + final_response,
                "sources": sources,
                "usage": _build_usage(),
            },
        )

        # stream_completed 요약 로그 (ADR-004 Tier 2, AC 6.1.8)
        duration_ms = round((time.perf_counter() - stream_start) * 1000, 2)
        logger.info(
            "stream_completed",
            session_id=request.session_id,
            duration_ms=duration_ms,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            nodes_executed=list(completed_nodes),
            sources_count=len(sources),
            langfuse_trace_id=langfuse_trace_id,
        )

    except BusinessException as e:
        # AC 2.6.5: Error 이벤트
        logger.warning("chat_workflow_error", error_code=e.error_code.code, detail=e.detail)
        yield format_sse("error", {"code": e.error_code.code, "msg": e.error_code.msg})
        # AC 2.7.8 / AC 6.1.6: 에러 시에도 sources 빈 배열 + 부분 누적 usage 포함
        yield format_sse(
            "done",
            {
                "code": e.error_code.code,
                "msg": e.error_code.msg,
                "response": sent_notice + "".join(partial_chunks),
                "sources": [],
                "usage": _build_usage(),
            },
        )

    except asyncio.CancelledError:
        # AC 2.6.8 / AC 6.1.6: 클라이언트 연결 해제 처리 + cancel 로그 부분 토큰
        duration_ms = round((time.perf_counter() - stream_start) * 1000, 2)
        logger.info(
            "stream_cancelled_by_client",
            session_id=request.session_id,
            duration_ms=duration_ms,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )
        raise

    except Exception as e:
        logger.error("chat_workflow_unexpected_error", error=str(e), exc_info=True)
        yield format_sse(
            "error",
            {"code": ErrorCode.INTERNAL_ERROR.code, "msg": ErrorCode.INTERNAL_ERROR.msg},
        )
        # AC 2.7.8 / AC 6.1.6: 에러 시에도 sources 빈 배열 + 부분 누적 usage 포함
        yield format_sse(
            "done",
            {
                "code": ErrorCode.INTERNAL_ERROR.code,
                "msg": ErrorCode.INTERNAL_ERROR.msg,
                "response": sent_notice + "".join(partial_chunks),
                "sources": [],
                "usage": _build_usage(),
            },
        )


# ============================================================================
# Chat Endpoint (AC 2.6.1)
# ============================================================================
@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """
    SSE 스트리밍 채팅 엔드포인트.

    Args:
        request: ChatRequest with query, session_id, history, user_id

    Returns:
        StreamingResponse with SSE events (thought, message, error, done)
    """
    logger.info(
        "chat_request_received",
        session_id=request.session_id,
        user_id=request.user_id,
        query_preview=request.query[:100],
        history_length=len(request.history),
        user_depts=request.user_depts,
        excluded_docs_count=len(request.excluded_docs),
    )

    return StreamingResponse(
        stream_workflow(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
