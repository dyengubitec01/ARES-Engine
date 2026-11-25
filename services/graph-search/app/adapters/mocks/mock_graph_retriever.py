"""테스트용 GraphRetriever 목."""

from app.core.interfaces import GraphRetrieverInterface


class MockGraphRetriever(GraphRetrieverInterface):
    """고정 결과를 반환하는 목. API/기동 테스트용."""

    def __init__(self, results: list[dict] | None = None) -> None:
        self._results = results if results is not None else [
            {
                "chunk_id": "chunk-1",
                "content": "본문 텍스트",
                "metadata": {
                    "doc_id": "doc-1",
                    "original_filename": "example.pdf",
                    "_source": "graph",
                },
                "score": 15.0,
                "hits": 3,
            }
        ]

    async def retrieve(self, query: str, trace_context: dict | None = None) -> list[dict]:
        return list(self._results)
