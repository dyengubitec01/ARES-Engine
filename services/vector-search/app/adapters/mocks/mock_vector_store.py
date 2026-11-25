"""Mock 벡터 스토어 어댑터 (테스트/개발용)."""

from app.core.interfaces import VectorStoreInterface
from app.core.payload_fields import PayloadField


class MockVectorStore(VectorStoreInterface):
    """테스트용 Mock 벡터 스토어.

    실제 Qdrant 연동 없이 더미 검색 결과를 반환한다.
    payload 구조는 실제 Qdrant 컬렉션과 동일한 형태이다.
    """

    @staticmethod
    def build_result(index: int) -> dict:
        """인덱스 기반 단일 mock 검색 결과를 생성한다.

        metadata 구조 변경 시 이 메서드만 수정하면
        MockVectorStore.search()와 모든 테스트가 자동으로 반영된다.
        """
        i = index
        return {
            "_point_id": f"mock-point-{i + 1:04d}",
            "content": (
                f"mock_doc_{i + 1}.pdf 페이지 {i + 1}-{i + 2} "
                f"Mock 문서 {i + 1}번 본문입니다."
            ),
            "metadata": {
                PayloadField.DOC_ID: f"doc-{i + 1:04d}",
                PayloadField.DOC_CONTENT_ID: f"dc-{i + 1:04d}",
                PayloadField.CHUNK_ID: f"chunk-{i + 1:04d}",
                PayloadField.CHUNK_INDEX: i,
                PayloadField.EMBEDDING_VERSION: "bge-m3-v1",
                PayloadField.ORIGINAL_FILENAME: f"mock_doc_{i + 1}.pdf",
                PayloadField.FILE_EXTENSION: ".pdf",
                PayloadField.MIME_TYPE: "application/pdf",
                PayloadField.LANGUAGE: None,
                PayloadField.FILE_MODIFIED_AT: "2026-01-12T00:00:00",
                PayloadField.PAGE_START: i + 1,
                PayloadField.PAGE_END: i + 2,
                PayloadField.SHEET_NAME: None,
                PayloadField.ROW_START: None,
                PayloadField.ROW_END: None,
                PayloadField.LOCATION_CONTEXT: f"페이지 {i + 1}-{i + 2}",
                PayloadField.DOCUMENT_CONTEXT: (
                    f"mock_doc_{i + 1}.pdf (페이지 {i + 1}-{i + 2})"
                ),
                PayloadField.TOKEN_COUNT: 200,
                PayloadField.TEXT_LENGTH: 850,
                PayloadField.TEXT_PREVIEW: f"Mock 문서 {i + 1}번 본문입니다…",
                PayloadField.AUTH_DEPT_ID: f"f5542890-753b-47f8-9dc8-9591cc4aa8{i:02d}",
                PayloadField.IS_ACTIVE: "Y",
            },
            "score": round(0.95 - (i * 0.05), 2),
        }

    async def search(
        self,
        query_vector: list[float],
        top_k: int,
        user_depts: list[str],
        excluded_docs: list[str] | None = None,
    ) -> list[dict]:
        """더미 dense 검색 결과를 생성하여 반환한다."""
        return [self.build_result(i) for i in range(top_k)]

    async def text_search(
        self,
        query_text: str,
        top_k: int,
        user_depts: list[str],
        excluded_docs: list[str] | None = None,
    ) -> list[dict]:
        """더미 full-text 검색 결과를 생성하여 반환한다.

        RRF overlap 경로를 검증할 수 있도록 짝수 인덱스는 dense와 동일한
        point_id(`mock-point-*`)를 재사용하고, 홀수 인덱스는 BM25 전용
        point_id(`mock-bm25-point-*`)를 사용한다. 결과 순서는 dense와 섞어
        rank 기반 RRF 합산이 의미 있게 동작하도록 한다.
        """
        results = []
        for i in range(top_k):
            item = self.build_result(i)
            # 짝수 rank는 dense와 공유, 홀수 rank는 BM25-only
            if i % 2 == 0:
                item["_point_id"] = f"mock-point-{i + 1:04d}"
            else:
                item["_point_id"] = f"mock-bm25-point-{i + 1:04d}"
            item["score"] = round(10.0 - (i * 0.5), 2)
            results.append(item)
        return results

    async def check_fulltext_index(self) -> bool:
        """Mock은 항상 인덱스가 존재하는 것으로 처리한다."""
        return True

    async def fetch_chunks_by_parents(
        self,
        parents_by_doc: dict[str, list[int]],
    ) -> list[dict]:
        """주어진 (문서, parent_id)별로 더미 청크를 생성해 반환한다.

        parent_id당 2개 청크(chunk_index 연속)를 생성하여 병합/정렬 검증을
        가능하게 한다. score는 부여하지 않는다(랭킹 아님).
        """
        chunks: list[dict] = []
        for doc_id, parent_ids in parents_by_doc.items():
            for pid in parent_ids:
                for j in range(2):
                    ci = pid * 10 + j
                    chunks.append({
                        "_point_id": f"{doc_id}-p{pid}-c{ci}",
                        "content": f"{doc_id} parent {pid} chunk {ci} 본문",
                        "metadata": {
                            PayloadField.DOC_CONTENT_ID: doc_id,
                            PayloadField.PARENT_ID: pid,
                            PayloadField.CHUNK_INDEX: ci,
                            PayloadField.ORIGINAL_FILENAME: f"{doc_id}.pdf",
                            PayloadField.LOCATION_CONTEXT: f"parent {pid}",
                            PayloadField.TEXT_PREVIEW: f"parent {pid} 미리보기",
                            PayloadField.IS_ACTIVE: "Y",
                        },
                    })
        return chunks
