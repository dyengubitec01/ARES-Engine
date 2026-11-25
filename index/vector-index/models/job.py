"""임베딩 Job 관련 모델"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any, Union
from uuid import UUID
from .enums import JobStatus


class JobPayload(BaseModel):
    """Kafka Job 페이로드"""
    job_id: Union[UUID, str]
    doc_content_id: Union[UUID, str] = Field(
        ..., description="이미 생성된 문서 컨텐츠 ID"
    )
    minio_bucket: str
    minio_object_key: str
    original_filename: str
    mime_type: str
    auth_dept_id: Union[UUID, str] = Field(..., description="요청자 부서 ID")
    extraction_version: Optional[str] = Field(default=None, description="텍스트 추출 파이프라인 버전 (예: v1.0.1)")
    embedding_profile: Optional[str] = Field(default="bge_m3_v1", description="임베딩 프로필 (bge_m3_v1 | bge_m3_hybrid_v2)")
    re_embedding: bool = Field(default=False, description="재임베딩 여부")
    re_embedding_reason: Optional[str] = Field(default=None, description="재임베딩 사유")
    embedding_mode: str = Field(
        default="re_chunk",
        description="재임베딩 처리 방식: re_chunk(텍스트 추출+청킹부터 다시) | re_vectorize(기존 청크 재활용, 벡터만 새로). 신규 ingest는 re_chunk 고정."
    )
    enable_ocr: bool = Field(
        default=False,
        description="OCR 활성화 (이미지/스캔 문서). 모든 지원 형식(PDF/DOC/DOCX/PPT/PPTX/XLSX/XLSM/HWP/HWPX)에서 동작 — Nemotron OCR v2 사용. OCR 텍스트는 본문 흐름 안에 inline 삽입되어 같은 청크에서 검색됨. XLS/CSV/TXT 등 이미지 없는 형식에서는 무시됨."
    )

    class Config:
        extra = "ignore"


class EmbeddingJob(BaseModel):
    """임베딩 Job 모델"""
    id: int
    doc_content_id: Union[UUID, str] = Field(
        ..., description="이미 생성된 문서 컨텐츠 ID"
    )
    kafka_topic: str
    kafka_key: str
    partition: Optional[int] = None
    kafka_offset: Optional[int] = None
    priority: int = 0
    retry_count: int = 0
    payload_json: Dict[str, Any]
    status: JobStatus
    enqueued_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    worker_id: Optional[str] = None
    error_message: Optional[str] = None





