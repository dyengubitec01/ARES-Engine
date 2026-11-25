"""Qdrant payload 필드명 정의 및 응답 metadata 필드 선택.

PayloadField Enum은 Qdrant payload 구조의 단일 정의 소스(Single Source of Truth)이다.
문자열 대신 Enum 멤버를 사용하면 오타 시 AttributeError가 발생한다.

PayloadField(str, Enum)이므로 문자열 키와의 비교·해시가 호환된다:
  "doc_id" in frozenset({PayloadField.DOC_ID})  → True
"""

from enum import Enum


class PayloadField(str, Enum):
    """Qdrant payload 필드명."""

    # === 식별자 ===
    DOC_ID = "doc_id"
    DOC_CONTENT_ID = "doc_content_id"
    CHUNK_ID = "chunk_id"
    CHUNK_INDEX = "chunk_index"
    PARENT_ID = "parent_id"

    # === 임베딩 ===
    EMBEDDING_VERSION = "embedding_version"

    # === 파일 정보 ===
    ORIGINAL_FILENAME = "original_filename"
    FILE_EXTENSION = "file_extension"
    MIME_TYPE = "mime_type"
    LANGUAGE = "language"
    FILE_MODIFIED_AT = "file_modified_at"

    # === 위치 ===
    PAGE_START = "page_start"
    PAGE_END = "page_end"
    SHEET_NAME = "sheet_name"
    ROW_START = "row_start"
    ROW_END = "row_end"
    LOCATION_CONTEXT = "location_context"
    DOCUMENT_CONTEXT = "document_context"

    # === 텍스트 ===
    TOKEN_COUNT = "token_count"
    TEXT_LENGTH = "text_length"
    TEXT_PREVIEW = "text_preview"
    TEXT_FOR_SEARCH = "text_for_search"

    # === 권한 ===
    AUTH_DEPT_ID = "auth_dept_id"

    # === 상태 ===
    IS_ACTIVE = "is_active"


RESPONSE_METADATA_FIELDS: frozenset[PayloadField] = frozenset({
    PayloadField.DOC_CONTENT_ID,
    PayloadField.ORIGINAL_FILENAME,
    PayloadField.LOCATION_CONTEXT,
    PayloadField.TEXT_PREVIEW,
})

RESPONSE_METADATA_KEY_MAP: dict[PayloadField, str] = {
    PayloadField.DOC_CONTENT_ID: "doc_id",
}
