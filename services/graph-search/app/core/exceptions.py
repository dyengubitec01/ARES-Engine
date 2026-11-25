"""RAGBaseException 예외 계층."""

from __future__ import annotations


class RAGBaseException(Exception):
    """모든 RAG 예외의 기반. code/msg 엔벨로프를 실어 나른다."""

    code: str = "RAG100050"
    msg: str = "내부 오류"

    def __init__(self, msg: str | None = None, code: str | None = None) -> None:
        if msg is not None:
            self.msg = msg
        if code is not None:
            self.code = code
        super().__init__(self.msg)


class BadRequestException(RAGBaseException):
    """잘못된 요청 (예: 빈 query)."""

    code = "RAG100040"
    msg = "잘못된 요청"


class GraphStoreException(RAGBaseException):
    """그래프 저장소 연동 실패. Fail-open 원칙상 대부분 흡수된다."""

    code = "RAG100060"
    msg = "그래프 저장소 연동 실패"
