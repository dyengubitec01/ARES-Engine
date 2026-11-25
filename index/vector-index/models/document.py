"""문서 관련 모델"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from .enums import DocumentStatus


class Document(BaseModel):
    """문서 모델"""
    id: int
    title: str
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class DocumentContent(BaseModel):
    """문서 컨텐츠 모델"""
    id: str
    document_id: int
    original_filename: str
    uploader_id: int
    sha256: str
    file_size: int
    mime_type: str
    language: Optional[str] = None
    encoding: Optional[str] = None
    status: DocumentStatus
    status_reason: Optional[str] = None
    status_message: Optional[str] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None








