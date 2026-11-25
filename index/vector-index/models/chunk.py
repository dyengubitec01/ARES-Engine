"""청크 관련 모델"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union, Literal
from uuid import UUID


class ChunkMetadata(BaseModel):
    """청크 메타데이터"""
    chunk_id: int
    doc_content_id: Union[UUID, str] = Field(
        ..., description="이미 생성된 문서 컨텐츠 ID"
    )
    chunk_index: int
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    token_count: int
    ref_hash: Optional[str] = None
    
    # 페이지 정보 (PDF, DOCX 등)
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    
    # 페이지 locator 타입 (실제 페이지 vs 추정 페이지 vs 섹션)
    locator_type: Optional[Literal["page", "page_estimated", "section"]] = None
    page_confidence: Optional[float] = None  # 페이지 추정 신뢰도 (0.0~1.0)
    page_source: Optional[str] = None  # 페이지 추정 방법 (footer_anchor, header_anchor, interpolation, fallback)
    
    # 시트/행 정보 (Excel, CSV 등)
    sheet_name: Optional[str] = None
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    
    # 추가 메타데이터
    metadata: Optional[Dict[str, Any]] = None


class Chunk(BaseModel):
    """청크 모델 (텍스트 포함)"""
    chunk_id: int
    doc_content_id: Union[UUID, str] = Field(
        ..., description="이미 생성된 문서 컨텐츠 ID"
    )
    chunk_index: int
    text: str
    token_count: int
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    locator_type: Optional[Literal["page", "page_estimated", "section"]] = None
    page_confidence: Optional[float] = None
    page_source: Optional[str] = None
    sheet_name: Optional[str] = None
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None






