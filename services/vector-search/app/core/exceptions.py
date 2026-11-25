"""커스텀 예외 클래스 정의.

모든 비즈니스 예외는 RAGBaseException을 상속하며,
글로벌 ExceptionHandler에서 RAGCode 기반 표준 에러 응답으로 변환된다.
"""

from app.api.responses import RAGCode


class RAGBaseException(Exception):
    """RAG 서버 기본 예외.

    모든 커스텀 예외의 부모 클래스.
    """

    def __init__(
        self,
        code: RAGCode = RAGCode.INTERNAL_ERROR,
        msg: str | None = None,
        status_code: int = 500,
    ) -> None:
        self.code = code
        self.msg = msg or code.default_message
        self.status_code = status_code
        super().__init__(self.msg)


class BadRequestException(RAGBaseException):
    """잘못된 요청 예외 (RAG100020)."""

    def __init__(self, msg: str | None = None) -> None:
        super().__init__(
            code=RAGCode.BAD_REQUEST,
            msg=msg,
            status_code=400,
        )


class EmbeddingException(RAGBaseException):
    """임베딩 API 연동 실패 예외 (RAG100040)."""

    def __init__(self, msg: str | None = None) -> None:
        super().__init__(
            code=RAGCode.EMBEDDING_FAILURE,
            msg=msg,
            status_code=502,
        )


class RerankerException(RAGBaseException):
    """리랭커 연동 실패 예외 (RAG100050)."""

    def __init__(self, msg: str | None = None) -> None:
        super().__init__(
            code=RAGCode.RERANKER_FAILURE,
            msg=msg,
            status_code=502,
        )


class VectorStoreException(RAGBaseException):
    """벡터 스토어 연동 실패 예외 (RAG100060)."""

    def __init__(self, msg: str | None = None) -> None:
        super().__init__(
            code=RAGCode.VECTOR_STORE_FAILURE,
            msg=msg,
            status_code=502,
        )


class InternalServerException(RAGBaseException):
    """서버 내부 오류 예외 (RAG100099)."""

    def __init__(self, msg: str | None = None) -> None:
        super().__init__(
            code=RAGCode.INTERNAL_ERROR,
            msg=msg,
            status_code=500,
        )
