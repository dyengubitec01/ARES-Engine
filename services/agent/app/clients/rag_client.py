"""
RAG Client Interface and Implementations - Story 2.3.

RAG(Retrieval-Augmented Generation) 클라이언트 인터페이스와 구현체 제공.
"""

from asyncio import Lock
from typing import Protocol, runtime_checkable

import httpx
import structlog
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.enums import ErrorCode
from app.core.exceptions import BusinessException

logger = structlog.get_logger()


class Document(BaseModel):
    """검색된 문서를 나타내는 모델 (AC 2.3.1).

    Attributes:
        content: 문서 내용
        metadata: 문서 메타데이터 (소스, 페이지 번호 등)
        score: 유사도 점수 (0.0 ~ 1.0)
    """

    content: str
    metadata: dict
    score: float


@runtime_checkable
class RAGClientProtocol(Protocol):
    """RAG Client 인터페이스 프로토콜 (AC 2.3.1).

    모든 RAG 클라이언트는 이 프로토콜을 구현해야 합니다.
    """

    async def search(
        self,
        query: str,
        trace_id: str | None = None,
        observation_id: str | None = None,
        user_depts: list[str] | None = None,
        excluded_docs: list[str] | None = None,
    ) -> list[Document]:
        """쿼리에 대한 관련 문서 검색.

        Args:
            query: 검색 쿼리
            trace_id: LangFuse trace_id (X-LF-Trace-ID 헤더)
            observation_id: LangFuse observation_id (X-LF-Parent-Id 헤더)
            user_depts: 사용자 부서 ID 목록
            excluded_docs: 제외할 문서 content-id 목록

        Returns:
            검색된 문서 목록 (유사도 점수 내림차순 정렬)
        """
        ...


class MockRAGClient:
    """Mock RAG Client 구현 (AC 2.3.2).

    개발 및 테스트용 Mock 클라이언트.
    하드코딩된 샘플 문서 목록을 반환합니다.
    """

    def __init__(self) -> None:
        """Mock RAG Client 초기화."""
        # 하드코딩된 샘플 문서 (3개 이상 시나리오)
        # Story 2.7: doc_id, title 추가
        self._sample_documents: list[Document] = [
            Document(
                content="인공지능(AI)은 컴퓨터 시스템이 인간의 지능을 모방하여 학습, 추론, 문제 해결 등의 작업을 수행하는 기술입니다.",
                metadata={
                    "doc_id": "doc-001",
                    "title": "AI 기초 가이드",
                    "source": "ai_basics.pdf",
                    "page": 1,
                    "category": "AI",
                },
                score=0.95,
            ),
            Document(
                content="머신러닝은 명시적인 프로그래밍 없이 데이터로부터 학습하는 AI의 한 분야입니다. 지도학습, 비지도학습, 강화학습으로 나뉩니다.",
                metadata={
                    "doc_id": "doc-002",
                    "title": "머신러닝 가이드",
                    "source": "ml_guide.pdf",
                    "page": 5,
                    "category": "ML",
                },
                score=0.88,
            ),
            Document(
                content="자연어 처리(NLP)는 컴퓨터가 인간의 언어를 이해하고 처리하는 기술입니다. 챗봇, 번역, 감성 분석 등에 활용됩니다.",
                metadata={
                    "doc_id": "doc-003",
                    "title": "NLP 핸드북",
                    "source": "nlp_handbook.pdf",
                    "page": 12,
                    "category": "NLP",
                },
                score=0.82,
            ),
            Document(
                content="딥러닝은 인공 신경망을 기반으로 하는 머신러닝의 한 분야로, 이미지 인식, 음성 인식 등에서 뛰어난 성능을 보입니다.",
                metadata={
                    "doc_id": "doc-004",
                    "title": "딥러닝 개론",
                    "source": "deep_learning.pdf",
                    "page": 3,
                    "category": "DL",
                },
                score=0.75,
            ),
            Document(
                content="RAG(Retrieval-Augmented Generation)는 검색 기반 생성 기법으로, LLM의 답변 품질을 향상시킵니다.",
                metadata={
                    "doc_id": "doc-005",
                    "title": "RAG 개요",
                    "source": "rag_overview.pdf",
                    "page": 1,
                    "category": "RAG",
                },
                score=0.70,
            ),
        ]

    async def search(
        self,
        query: str,
        trace_id: str | None = None,
        observation_id: str | None = None,
        user_depts: list[str] | None = None,
        excluded_docs: list[str] | None = None,
    ) -> list[Document]:
        """쿼리에 대한 관련 문서 검색 (Mock 구현).

        실제 검색 없이 하드코딩된 샘플 문서를 반환합니다.
        문서는 score 기준 내림차순으로 정렬되어 있습니다.

        Args:
            query: 검색 쿼리 (Mock에서는 무시됨)
            trace_id: LangFuse trace_id (Mock에서는 무시됨)
            observation_id: LangFuse observation_id (Mock에서는 무시됨)
            user_depts: 사용자 부서 ID 목록 (Mock에서는 무시됨)
            excluded_docs: 제외할 문서 content-id 목록 (Mock에서는 무시됨)

        Returns:
            샘플 문서 목록 (점수 내림차순). 쿼리에 "검색결과없음" 포함 시 빈 목록.
        """
        # 0건 시나리오 검증용 트리거 (E2E에서 검색 0건 경로 실행 가능하게)
        if "검색결과없음" in query:
            return []
        sorted_docs = sorted(self._sample_documents, key=lambda d: d.score, reverse=True)
        return sorted_docs


class RAGClient:
    """Real RAG Client 스켈레톤 (AC 2.3.3).

    실제 RAG 서버와 통신하는 클라이언트 (미구현 스켈레톤).
    httpx.AsyncClient를 사용하여 비동기 HTTP 통신을 수행합니다.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """RAG Client 초기화.

        Args:
            base_url: RAG 서버 기본 URL. None이면 설정에서 로드.
            timeout: 요청 타임아웃(초). None이면 설정에서 로드.
        """
        settings = get_settings()
        self.base_url = base_url or settings.RAG_BASE_URL
        self.timeout = timeout or settings.RAG_TIMEOUT
        self._client: httpx.AsyncClient | None = None
        self._client_lock = Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 인스턴스 반환 (Lazy 초기화, Thread-safe).

        Returns:
            httpx.AsyncClient 인스턴스
        """
        async with self._client_lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout,
                )
        return self._client

    async def search(
        self,
        query: str,
        trace_id: str | None = None,
        observation_id: str | None = None,
        user_depts: list[str] | None = None,
        excluded_docs: list[str] | None = None,
    ) -> list[Document]:
        """쿼리에 대한 관련 문서 검색 (AC 2.8.8: 실제 서버 연동).

        POST {RAG_BASE_URL}/v1/search 엔드포인트를 호출한다.
        RAG 서버가 rerank 후 최적의 문서 수를 결정하므로 응답 전체를 수용한다.

        Args:
            query: 검색 쿼리
            trace_id: LangFuse trace_id (X-LF-Trace-ID 헤더)
            observation_id: LangFuse observation_id (X-LF-Parent-Id 헤더)
            user_depts: 사용자 부서 ID 목록
            excluded_docs: 제외할 문서 content-id 목록

        Returns:
            검색된 문서 목록

        Raises:
            BusinessException: RAG 서버 호출 실패 시
        """
        client = await self._get_client()
        headers: dict[str, str] = {}
        if trace_id:
            headers["X-LF-Trace-ID"] = trace_id
        if observation_id:
            headers["X-LF-Parent-Id"] = observation_id

        try:
            body: dict = {"query": query}
            if user_depts:
                body["user_depts"] = user_depts
            if excluded_docs:
                body["excluded_docs"] = excluded_docs

            response = await client.post(
                "/v1/search",
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

            # AC 2.8.13: RAG 응답 → Document 매핑
            results = data.get("data", {}).get("results", [])
            documents: list[Document] = []
            for result in results:
                metadata = result.get("metadata", {})
                doc = Document(
                    content=result.get("content", ""),
                    metadata={
                        "doc_id": metadata.get("doc_id", ""),
                        "source": metadata.get("original_filename", ""),
                        "title": metadata.get("original_filename", ""),
                        "location": metadata.get("location_context", ""),
                    },
                    score=result.get("score", 0.0),
                )
                documents.append(doc)

            logger.info(
                "rag_search_completed",
                results_count=len(documents),
                query_preview=query[:100],
                user_depts=user_depts,
                excluded_docs_count=len(excluded_docs) if excluded_docs else 0,
            )
            return documents

        except httpx.TimeoutException as e:
            raise BusinessException(
                ErrorCode.RAG_SEARCH, detail=f"RAG 서버 타임아웃: {e}",
            ) from e
        except httpx.HTTPStatusError as e:
            raise BusinessException(
                ErrorCode.RAG_SEARCH, detail=f"RAG 서버 HTTP 오류: {e.response.status_code}",
            ) from e
        except httpx.ConnectError as e:
            raise BusinessException(
                ErrorCode.RAG_SEARCH, detail=f"RAG 서버 연결 실패: {e}",
            ) from e
        except Exception as e:
            raise BusinessException(
                ErrorCode.RAG_SEARCH, detail=f"RAG 검색 실패: {e}",
            ) from e

    async def close(self) -> None:
        """HTTP 클라이언트 연결 종료."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "RAGClient":
        """Context Manager 진입."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context Manager 종료 - 리소스 자동 정리."""
        await self.close()


def get_rag_client() -> MockRAGClient | RAGClient:
    """RAG Client 팩토리 함수 (AC 2.3.4).

    Settings의 USE_MOCK_RAG 설정에 따라 적절한 클라이언트를 반환합니다.

    Returns:
        USE_MOCK_RAG=True: MockRAGClient
        USE_MOCK_RAG=False: RAGClient
    """
    settings = get_settings()

    if settings.USE_MOCK_RAG:
        return MockRAGClient()

    return RAGClient(
        base_url=settings.RAG_BASE_URL,
        timeout=settings.RAG_TIMEOUT,
    )


def format_documents_to_sources(documents: list[Document]) -> list[dict]:
    """검색된 문서를 출처 정보로 변환 (Story 2.7, AC 2.7.6).

    문서를 done 이벤트에 포함할 sources 형태로 변환합니다.

    Args:
        documents: 변환할 문서 목록

    Returns:
        출처 정보 목록 [{doc_id, doc_title, doc_content, location}, ...]
    """
    if not documents:
        return []

    sources: list[dict] = []
    for doc in documents:
        source = {
            "doc_id": doc.metadata.get("doc_id", ""),
            "doc_title": doc.metadata.get("title", doc.metadata.get("source", "")),
            "doc_content": doc.content,
            "location": doc.metadata.get("location", ""),
        }
        sources.append(source)

    return sources


def format_documents_for_context(documents: list[Document]) -> list[str]:
    """검색된 문서를 컨텍스트용 문자열로 포맷팅 (AC 2.3.5).

    문서 내용을 <document> 태그로 감싸 LLM이 문서 경계를 명확히 구분할 수 있도록 합니다.
    문서 번호나 출처 정보는 포함하지 않아 LLM 답변에 노출되지 않습니다.
    참조 문서 정보는 SSE done 이벤트에서 별도로 제공됩니다.

    Args:
        documents: 포맷팅할 문서 목록

    Returns:
        포맷팅된 문자열 목록

    Example:
        >>> docs = [Document(content="Hello", metadata={"source": "test.pdf"}, score=0.9)]
        >>> format_documents_for_context(docs)
        ['<document>\\nHello\\n</document>']
    """
    if not documents:
        return []

    formatted: list[str] = []

    for doc in documents:
        formatted.append(f"<document>\n{doc.content}\n</document>")

    return formatted
