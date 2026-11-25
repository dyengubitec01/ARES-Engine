"""RAGCode 코드 상수 + APIResponse 엔벨로프 헬퍼."""

from __future__ import annotations

from enum import Enum
from typing import Any


class RAGCode(str, Enum):
    SEARCH_SUCCESS = "RAG100000"
    NO_RESULT = "RAG100001"
    BAD_REQUEST = "RAG100040"
    GRAPH_STORE_ERROR = "RAG100060"


_MESSAGES = {
    RAGCode.SEARCH_SUCCESS: "그래프 검색 성공",
    RAGCode.NO_RESULT: "검색 결과 없음",
    RAGCode.BAD_REQUEST: "잘못된 요청",
    RAGCode.GRAPH_STORE_ERROR: "그래프 저장소 연동 실패",
}


def api_response(code: RAGCode, data: dict | None = None, msg: str | None = None) -> dict:
    body: dict[str, Any] = {"code": code.value, "msg": msg or _MESSAGES[code]}
    if data is not None:
        body["data"] = data
    return body


def success_response(data: dict) -> dict:
    return api_response(RAGCode.SEARCH_SUCCESS, data=data)


def no_result_response() -> dict:
    return api_response(RAGCode.NO_RESULT)


def error_response(code: RAGCode, msg: str | None = None) -> dict:
    return api_response(code, msg=msg)
