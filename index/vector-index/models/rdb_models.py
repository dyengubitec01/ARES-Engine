"""PostgreSQL ORM 모델 정의"""
from __future__ import annotations

import uuid
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID as PGUUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

from models.enums import (
    DocumentStatus,
    JobStatus,
    ObjectKind,
    DistanceMetric,
    UserRole,
    EventSource,
)

Base = declarative_base()

doc_status_enum = ENUM(
    *(status.value for status in DocumentStatus),
    name="doc_status",
    create_type=False,
)
job_status_enum = ENUM(
    *(status.value for status in JobStatus),
    name="job_status",
    create_type=False,
)
object_kind_enum = ENUM(
    *(kind.value for kind in ObjectKind),
    name="object_kind",
    create_type=False,
)
distance_metric_enum = ENUM(
    *(metric.value for metric in DistanceMetric),
    name="distance_metric",
    create_type=False,
)
user_role_enum = ENUM(
    *(role.value for role in UserRole),
    name="user_role",
    create_type=False,
)
event_source_enum = ENUM(
    *(source.value for source in EventSource),
    name="event_source",
    create_type=False,
)


class AuthUser(Base):
    """사용자"""

    __tablename__ = "auth_users"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    email = Column(String(320), nullable=False, unique=True)
    name = Column(String(100))
    auth_dept_id = Column(PGUUID(as_uuid=True))
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    job_title = Column(String(100))


class DocDocument(Base):
    """문서 메타"""

    __tablename__ = "doc_documents"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    title = Column(String(512), nullable=False)
    minio_url = Column(Text, nullable=False)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("auth_users.id"), nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class DocDocumentContent(Base):
    """문서 컨텐츠"""

    __tablename__ = "doc_document_content"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    document_id = Column(PGUUID(as_uuid=True), ForeignKey("doc_documents.id"), nullable=False, index=True)
    original_filename = Column(Text, nullable=False)
    uploader_id = Column(PGUUID(as_uuid=True), ForeignKey("auth_users.id"), nullable=False)
    auth_dept_id = Column(PGUUID(as_uuid=True))
    sha256 = Column(String(64))
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(Text, nullable=False)
    language = Column(Text)
    encoding = Column(Text)
    status = Column(doc_status_enum, nullable=False, index=True)
    status_reason = Column(Text)
    status_message = Column(Text)
    file_modified_at = Column(DateTime(timezone=False))
    queued_at = Column(DateTime(timezone=False))
    started_at = Column(DateTime(timezone=False))
    finished_at = Column(DateTime(timezone=False))
    requested_at = Column(DateTime(timezone=False))
    # 문서 버전·soft삭제 (BE 관리 컬럼. 2026-06-16 실테이블과 ORM 정합화)
    version_no = Column(Integer, nullable=False, server_default=text("1"))
    is_active = Column(String(1), nullable=False, server_default=func.text("'Y'"))  # 'Y' 활성 / 'N' soft삭제
    deleted_at = Column(DateTime(timezone=False))  # soft삭제 시각 (is_active='N'과 짝)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), onupdate=func.now())


class RagEmbeddingJob(Base):
    """임베딩 작업"""

    __tablename__ = "rag_embedding_jobs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    doc_content_id = Column(PGUUID(as_uuid=True), ForeignKey("doc_document_content.id"), nullable=False, index=True)
    kafka_topic = Column(String(255), nullable=False)
    kafka_key = Column(String(255), nullable=False)
    partition = Column(Integer)
    kafka_offset = Column("offset", BigInteger)
    priority = Column(Integer, nullable=False, default=0)
    retry_count = Column(Integer, nullable=False, default=0)
    payload_json = Column(JSONB, nullable=False)
    status = Column(job_status_enum, nullable=False, index=True)
    enqueued_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=False))
    finished_at = Column(DateTime(timezone=False))
    worker_id = Column(String(128))
    error_message = Column(Text)
    minio_original_filename = Column(String(255), nullable=True)
    minio_mime_type = Column(String(128), nullable=True)
    minio_file_size = Column(BigInteger, nullable=True)


class RagStatusEvent(Base):
    """상태 이벤트"""

    __tablename__ = "rag_status_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    doc_content_id = Column(PGUUID(as_uuid=True), ForeignKey("doc_document_content.id"), nullable=False, index=True)
    job_id = Column(PGUUID(as_uuid=True), ForeignKey("rag_embedding_jobs.id"), index=True)
    source = Column(event_source_enum, nullable=False)
    category = Column(String(32), nullable=False, default="job")
    message = Column(Text)
    metadata_json = Column("metadata", JSONB)
    status = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class RagChunk(Base):
    """청크"""

    __tablename__ = "rag_chunks"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    doc_content_id = Column(PGUUID(as_uuid=True), ForeignKey("doc_document_content.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    embedding_version = Column(String(64), nullable=False, default="bge-m3-v1", index=True)
    extraction_version = Column(String(64), nullable=True)
    start_char = Column(Integer)
    end_char = Column(Integer)
    token_count = Column(Integer, nullable=False)
    ref_hash = Column(String(128))
    text = Column(Text, nullable=False)
    text_checksum = Column(String(128), nullable=False)
    text_hash = Column(String(128), nullable=False)
    page_start = Column(Integer)
    page_end = Column(Integer)
    sheet_name = Column(String(255))
    row_start = Column(Integer)
    row_end = Column(Integer)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("doc_content_id", "chunk_index", name="uq_chunk_content_index"),
    )


class RagProcessingStat(Base):
    """처리 통계"""

    __tablename__ = "rag_processing_stats"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    doc_content_id = Column(PGUUID(as_uuid=True), ForeignKey("doc_document_content.id"), nullable=False, unique=True)
    model_name = Column(String(128), nullable=False)
    model_version = Column(String(128), nullable=False)
    vector_dim = Column(Integer, nullable=False)
    total_chunks = Column(Integer, nullable=False)
    success_chunks = Column(Integer, nullable=False)
    failed_chunks = Column(Integer, nullable=False, default=0)
    total_tokens = Column(BigInteger, nullable=False, default=0)
    embed_ms = Column(BigInteger, nullable=False, default=0)
    content_type = Column(String(255), nullable=False, default="application/octet-stream")
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class RagUpsertHistory(Base):
    """Qdrant 업서트 이력"""

    __tablename__ = "rag_upsert_history"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    doc_content_id = Column(PGUUID(as_uuid=True), ForeignKey("doc_document_content.id"), nullable=False, index=True)
    chunk_id = Column(PGUUID(as_uuid=True), ForeignKey("rag_chunks.id"), nullable=False)
    job_id = Column(PGUUID(as_uuid=True), ForeignKey("rag_embedding_jobs.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    qdrant_collection_name = Column(String(255), nullable=False)
    qdrant_point_id = Column(String(128), nullable=False)
    vector_dim = Column(Integer, nullable=False)
    status = Column(job_status_enum, nullable=False)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class RagEmbeddingsIndex(Base):
    """임베딩 인덱스"""

    __tablename__ = "rag_embeddings_index"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    doc_content_id = Column(PGUUID(as_uuid=True), ForeignKey("doc_document_content.id"), nullable=False)
    chunk_id = Column(PGUUID(as_uuid=True), ForeignKey("rag_chunks.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    embedding_version = Column(String(64), nullable=False, default="bge-m3-v1", index=True)
    qdrant_collection_name = Column(String(255), nullable=False)
    qdrant_point_id = Column(String(255), nullable=False)
    vector_dim = Column(Integer, nullable=False)
    qdrant_vector_checksum = Column(String(128))
    qdrant_payload_checksum = Column(String(128))
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("doc_content_id", "chunk_index", "embedding_version", name="uq_embeddings_index_v"),
    )


class StorageObjectFile(Base):
    """MinIO 객체 메타"""

    __tablename__ = "storage_object_files"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    doc_content_id = Column(PGUUID(as_uuid=True), ForeignKey("doc_document_content.id"), nullable=False, index=True)
    kind = Column(object_kind_enum, nullable=False)
    bucket = Column(String(63), nullable=False)
    object_key = Column(Text, nullable=False)
    etag = Column(String(64))
    sha256 = Column(String(64))
    size_bytes = Column(BigInteger, nullable=False)
    metadata_json = Column("metadata", JSONB, nullable=False, default={})
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    created_by = Column(PGUUID(as_uuid=True), ForeignKey("auth_users.id"))
    content_type = Column(String(255))

    __table_args__ = (
        UniqueConstraint("bucket", "object_key", name="uq_storage_bucket_key"),
    )


class RagQdrantCollection(Base):
    """Qdrant 컬렉션"""

    __tablename__ = "vec_qdrant_collections"

    name = Column(String(100), primary_key=True)
    vector_dim = Column(Integer, nullable=False)
    metric = Column(distance_metric_enum, nullable=False)
    shard_count = Column(Integer, nullable=False)
    replication_factor = Column(Integer, nullable=False)
    write_consistency = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class RagSimilarityCheck(Base):
    """유사도 검증 결과"""

    __tablename__ = "rag_similarity_checks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    doc_content_id = Column(PGUUID(as_uuid=True), ForeignKey("doc_document_content.id"), nullable=False, index=True)
    job_id = Column(PGUUID(as_uuid=True), ForeignKey("rag_embedding_jobs.id"))
    sample_count = Column(Integer, nullable=False)
    high_similarity_matches = Column(Integer, nullable=False, default=0)
    similarity_threshold = Column(Float, nullable=False)
    match_ratio = Column(Float, nullable=False, default=0.0)
    avg_similarity = Column(Float, nullable=False, default=0.0)
    similar_documents = Column(JSONB)
    details = Column(JSONB)
    memo = Column(Text)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)


class AuthUsersDept(Base):
    """부서"""

    __tablename__ = "auth_users_dept"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=func.text("uuid_generate_v4()"))
    dept_name = Column(String(100), nullable=False, default="미지정부서")
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
