"""처리 통계 모델"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Union
from uuid import UUID


class ProcessingStats(BaseModel):
    """처리 통계 모델"""
    id: int
    doc_content_id: Union[UUID, str] = Field(
        ..., description="이미 생성된 문서 컨텐츠 ID"
    )
    model_name: str
    model_version: str
    vector_dim: int
    total_chunks: int
    success_chunks: int
    failed_chunks: int
    total_tokens: int
    embed_ms: Optional[int] = None  # 임베딩 소요 시간 (밀리초)
    created_at: datetime






