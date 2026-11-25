"""Repository 패턴 구현"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from sqlalchemy.orm import Session
from uuid import UUID, uuid4

from models.rdb_models import (
    DocDocument,
    DocDocumentContent,
    RagChunk,
    RagEmbeddingJob,
    RagEmbeddingsIndex,
    RagProcessingStat,
    RagSimilarityCheck,
    RagStatusEvent,
    RagUpsertHistory,
    StorageObjectFile,
)
from models.enums import DocumentStatus, JobStatus, ObjectKind

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.utcnow()


def _normalize_job_id(job_id: Any) -> uuid.UUID:
    if isinstance(job_id, uuid.UUID):
        return job_id
    if job_id is None:
        raise ValueError("job_id가 필요합니다.")
    return uuid.UUID(str(job_id))


def _ensure_uuid(value: Union[str, UUID]) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


class DocumentRepository:
    """문서 Repository"""

    @staticmethod
    def get_by_id(session: Session, doc_id: int) -> Optional[DocDocument]:
        return session.get(DocDocument, doc_id)

    @staticmethod
    def create(
        session: Session,
        title: str,
        created_by: int,
    ) -> DocDocument:
        document = DocDocument(title=title, created_by=created_by)
        session.add(document)
        session.flush()
        return document


class DocumentContentRepository:
    """문서 컨텐츠 Repository"""

    @staticmethod
    def get_by_id(session: Session, content_id: Union[str, UUID]) -> Optional[DocDocumentContent]:
        return session.get(DocDocumentContent, _ensure_uuid(content_id))

    @staticmethod
    def get_by_sha256(session: Session, sha256: str) -> Optional[DocDocumentContent]:
        """SHA-256으로 문서 컨텐츠 조회 (첫 번째 결과만 반환)"""
        return (
            session.query(DocDocumentContent)
            .filter(DocDocumentContent.sha256 == sha256)
            .first()
        )

    @staticmethod
    def get_completed_by_sha256(session: Session, sha256: str) -> Optional[DocDocumentContent]:
        """SHA-256으로 임베딩 완료된 문서 컨텐츠 조회"""
        return (
            session.query(DocDocumentContent)
            .filter(
                DocDocumentContent.sha256 == sha256,
                DocDocumentContent.status == DocumentStatus.COMPLETED.value
            )
            .first()
        )

    @staticmethod
    def create(
        session: Session,
        document_id: int,
        uploader_id: int,
        original_filename: str,
        sha256: str,
        file_size: int,
        mime_type: str,
        language: Optional[str] = None,
        encoding: Optional[str] = None,
        status: DocumentStatus = DocumentStatus.UPLOADED,
    ) -> DocDocumentContent:
        content = DocDocumentContent(
            document_id=document_id,
            uploader_id=uploader_id,
            original_filename=original_filename,
            sha256=sha256,
            file_size=file_size,
            mime_type=mime_type,
            language=language,
            encoding=encoding,
            status=status.value,
        )
        session.add(content)
        session.flush()
        return content

    @staticmethod
    def update_status(
        session: Session,
        content_id: Union[str, UUID],
        status: DocumentStatus,
        status_reason: Optional[str] = None,
        status_message: Optional[str] = None,
    ) -> bool:
        content = session.get(DocDocumentContent, _ensure_uuid(content_id))
        if not content:
            logger.warning("문서 컨텐츠를 찾을 수 없습니다: content_id=%s", content_id)
            return False

        now = _now()
        content.status = status.value
        content.updated_at = now

        if status_reason:
            content.status_reason = status_reason
        if status_message:
            content.status_message = status_message

        if status == DocumentStatus.QUEUED:
            content.queued_at = now
        elif status in (DocumentStatus.PARSING, DocumentStatus.EMBEDDING):
            if not content.started_at:
                content.started_at = now
        elif status in (DocumentStatus.COMPLETED, DocumentStatus.FAILED, DocumentStatus.DUPLICATED):
            content.finished_at = now

        session.flush()
        return True


class EmbeddingJobRepository:
    """임베딩 Job Repository"""

    @staticmethod
    def get_by_id(session: Session, job_id: Any) -> Optional[RagEmbeddingJob]:
        normalized = _normalize_job_id(job_id)
        return session.get(RagEmbeddingJob, normalized)

    @staticmethod
    def create(
        session: Session,
        *,
        doc_content_id: Union[str, UUID],
        kafka_topic: str,
        kafka_key: str,
        payload_json: Dict[str, Any],
        priority: int = 0,
        status: JobStatus = JobStatus.QUEUED,
        job_id: Optional[uuid.UUID] = None,
    ) -> RagEmbeddingJob:
        identifier = job_id or uuid4()
        job = RagEmbeddingJob(
            id=identifier,
            doc_content_id=_ensure_uuid(doc_content_id),
            kafka_topic=kafka_topic,
            kafka_key=kafka_key,
            payload_json=payload_json,
            priority=priority,
            status=status.value,
        )
        session.add(job)
        session.flush()
        return job

    @staticmethod
    def update_status(
        session: Session,
        job_id: Any,
        status: JobStatus,
        *,
        worker_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        job = EmbeddingJobRepository.get_by_id(session, job_id)
        if not job:
            logger.warning("임베딩 Job을 찾을 수 없습니다: job_id=%s", job_id)
            return False

        now = _now()
        job.status = status.value

        if worker_id:
            job.worker_id = worker_id

        if error_message:
            job.error_message = error_message[:2000]

        if status == JobStatus.STARTED and not job.started_at:
            job.started_at = now
        if status in (JobStatus.DONE, JobStatus.FAILED):
            job.finished_at = now

        session.flush()
        return True

    @staticmethod
    def update_kafka_metadata(
        session: Session,
        job_id: Any,
        partition: int,
        offset: int,
    ) -> bool:
        """Kafka partition과 offset 정보 업데이트"""
        job = EmbeddingJobRepository.get_by_id(session, job_id)
        if not job:
            logger.warning("임베딩 Job을 찾을 수 없습니다: job_id=%s", job_id)
            return False

        job.partition = partition
        job.kafka_offset = offset
        session.flush()
        return True

    @staticmethod
    def increment_retry_count(session: Session, job_id: Any) -> int:
        """재시도 카운트를 증가시키고 현재 값 반환"""
        job = EmbeddingJobRepository.get_by_id(session, job_id)
        if not job:
            logger.warning("임베딩 Job을 찾을 수 없습니다: job_id=%s", job_id)
            return -1

        job.retry_count += 1
        session.flush()
        return job.retry_count

    @staticmethod
    def get_pending_jobs(session: Session, limit: int = 10) -> List[RagEmbeddingJob]:
        return (
            session.query(RagEmbeddingJob)
            .filter(RagEmbeddingJob.status == JobStatus.QUEUED.value)
            .order_by(RagEmbeddingJob.enqueued_at.asc())
            .limit(limit)
            .all()
        )


class StatusEventRepository:
    """상태 이벤트 기록"""

    @staticmethod
    def record(
        session: Session,
        *,
        doc_content_id: Union[str, UUID],
        job_id: Optional[Any],
        status: str,
        source: str,
        category: str = "job",
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RagStatusEvent:
        normalized_job_id = None
        if job_id:
            normalized_job_id = _normalize_job_id(job_id)

        event = RagStatusEvent(
            doc_content_id=_ensure_uuid(doc_content_id),
            job_id=normalized_job_id,
            category=category,
            status=status,
            source=source,
            message=message,
            metadata_json=metadata or {},
        )
        session.add(event)
        session.flush()
        return event


class ChunkRepository:
    """청크 Repository"""

    @staticmethod
    def create_batch(
        session: Session,
        *,
        doc_content_id: Union[str, UUID],
        chunk_inputs: Sequence[Dict[str, Any]],
    ) -> List[RagChunk]:
        if not chunk_inputs:
            return []

        doc_content_uuid = _ensure_uuid(doc_content_id)
        chunk_indexes = [c["chunk_index"] for c in chunk_inputs]

        # 청크 row는 dense/hybrid가 공유하므로 (doc_content_id, chunk_index)로만 식별
        existing = (
            session.query(RagChunk)
            .filter(
                RagChunk.doc_content_id == doc_content_uuid,
                RagChunk.chunk_index.in_(chunk_indexes),
            )
            .all()
        )
        existing_map = {(row.chunk_index): row for row in existing}

        upserted: List[RagChunk] = []
        for chunk in chunk_inputs:
            instance = existing_map.get(chunk["chunk_index"])
            if instance:
                instance.start_char = chunk.get("start_char")
                instance.end_char = chunk.get("end_char")
                instance.token_count = chunk["token_count"]
                instance.ref_hash = chunk.get("ref_hash")
                instance.text = chunk["text"]
                instance.text_checksum = chunk["text_checksum"]
                instance.text_hash = chunk.get("text_hash") or chunk["text_checksum"]
                instance.page_start = chunk.get("page_start")
                instance.page_end = chunk.get("page_end")
                instance.sheet_name = chunk.get("sheet_name")
                instance.row_start = chunk.get("row_start")
                instance.row_end = chunk.get("row_end")
                instance.metadata_json = chunk.get("metadata")
                instance.extraction_version = chunk.get("extraction_version")
                upserted.append(instance)
                continue

            instance = RagChunk(
                doc_content_id=doc_content_uuid,
                chunk_index=chunk["chunk_index"],
                embedding_version=chunk.get("embedding_version", "bge-m3-v1"),
                extraction_version=chunk.get("extraction_version"),
                start_char=chunk.get("start_char"),
                end_char=chunk.get("end_char"),
                token_count=chunk["token_count"],
                ref_hash=chunk.get("ref_hash"),
                text=chunk["text"],
                text_checksum=chunk["text_checksum"],
                text_hash=chunk.get("text_hash") or chunk["text_checksum"],
                page_start=chunk.get("page_start"),
                page_end=chunk.get("page_end"),
                sheet_name=chunk.get("sheet_name"),
                row_start=chunk.get("row_start"),
                row_end=chunk.get("row_end"),
                metadata_json=chunk.get("metadata"),
            )
            session.add(instance)
            upserted.append(instance)

        session.flush()
        return upserted

    @staticmethod
    def get_by_doc_content(session: Session, doc_content_id: Union[str, UUID]) -> List[RagChunk]:
        return (
            session.query(RagChunk)
            .filter(RagChunk.doc_content_id == _ensure_uuid(doc_content_id))
            .order_by(RagChunk.chunk_index.asc())
            .all()
        )

    @staticmethod
    def delete_by_doc_content(session: Session, doc_content_id: Union[str, UUID]) -> int:
        """문서 컨텐츠의 모든 청크 삭제, 삭제된 행 수 반환"""
        count = (
            session.query(RagChunk)
            .filter(RagChunk.doc_content_id == _ensure_uuid(doc_content_id))
            .delete(synchronize_session="fetch")
        )
        session.flush()
        return count


class ProcessingStatsRepository:
    """처리 통계 Repository"""

    @staticmethod
    def upsert(
        session: Session,
        *,
        doc_content_id: Union[str, UUID],
        model_name: str,
        model_version: str,
        vector_dim: int,
        total_chunks: int,
        success_chunks: int,
        failed_chunks: int,
        total_tokens: int,
        embed_ms: Optional[int] = None,
    ) -> RagProcessingStat:
        doc_content_uuid = _ensure_uuid(doc_content_id)
        existing = (
            session.query(RagProcessingStat)
            .filter(RagProcessingStat.doc_content_id == doc_content_uuid)
            .one_or_none()
        )
        if existing:
            existing.model_name = model_name
            existing.model_version = model_version
            existing.vector_dim = vector_dim
            existing.total_chunks = total_chunks
            existing.success_chunks = success_chunks
            existing.failed_chunks = failed_chunks
            existing.total_tokens = total_tokens
            existing.embed_ms = embed_ms
            session.flush()
            return existing

        stats = RagProcessingStat(
            doc_content_id=doc_content_uuid,
            model_name=model_name,
            model_version=model_version,
            vector_dim=vector_dim,
            total_chunks=total_chunks,
            success_chunks=success_chunks,
            failed_chunks=failed_chunks,
            total_tokens=total_tokens,
            embed_ms=embed_ms,
        )
        session.add(stats)
        session.flush()
        return stats

    @staticmethod
    def get_by_doc_content(session: Session, doc_content_id: Union[str, UUID]) -> Optional[RagProcessingStat]:
        return (
            session.query(RagProcessingStat)
            .filter(RagProcessingStat.doc_content_id == _ensure_uuid(doc_content_id))
            .one_or_none()
        )

    @staticmethod
    def delete_by_doc_content(session: Session, doc_content_id: Union[str, UUID]) -> int:
        """문서 컨텐츠의 처리 통계 삭제, 삭제된 행 수 반환"""
        count = (
            session.query(RagProcessingStat)
            .filter(RagProcessingStat.doc_content_id == _ensure_uuid(doc_content_id))
            .delete(synchronize_session="fetch")
        )
        session.flush()
        return count


class UpsertHistoryRepository:
    """Qdrant 업서트 이력 Repository"""

    @staticmethod
    def create_batch(
        session: Session,
        entries: Sequence[Dict[str, Any]],
    ) -> List[RagUpsertHistory]:
        models: List[RagUpsertHistory] = []
        for entry in entries:
            models.append(
                RagUpsertHistory(
                    job_id=_normalize_job_id(entry["job_id"]),
                    doc_content_id=_ensure_uuid(entry["doc_content_id"]),
                    chunk_id=entry["chunk_id"],
                    chunk_index=entry["chunk_index"],
                    qdrant_collection_name=entry["qdrant_collection_name"],
                    qdrant_point_id=entry["qdrant_point_id"],
                    status=entry["status"],
                    error_message=entry.get("error_message"),
                    vector_dim=entry.get("vector_dim"),
                )
            )
        if not models:
            return []
        session.add_all(models)
        session.flush()
        return models

    @staticmethod
    def delete_by_doc_content(session: Session, doc_content_id: Union[str, UUID]) -> int:
        """문서 컨텐츠의 모든 업서트 이력 삭제, 삭제된 행 수 반환"""
        count = (
            session.query(RagUpsertHistory)
            .filter(RagUpsertHistory.doc_content_id == _ensure_uuid(doc_content_id))
            .delete(synchronize_session="fetch")
        )
        session.flush()
        return count


class EmbeddingsIndexRepository:
    """임베딩 인덱스 Repository"""

    @staticmethod
    def upsert_many(
        session: Session,
        entries: Sequence[Dict[str, Any]],
    ) -> List[RagEmbeddingsIndex]:
        if not entries:
            return []

        doc_content_uuid = _ensure_uuid(entries[0]["doc_content_id"])
        chunk_indexes = [entry["chunk_index"] for entry in entries]
        # 한 번의 upsert는 단일 embedding_version에 대한 것이므로 첫 항목 기준
        embedding_version = entries[0].get("embedding_version", "bge-m3-v1")

        existing = (
            session.query(RagEmbeddingsIndex)
            .filter(
                RagEmbeddingsIndex.doc_content_id == doc_content_uuid,
                RagEmbeddingsIndex.chunk_index.in_(chunk_indexes),
                RagEmbeddingsIndex.embedding_version == embedding_version,
            )
            .all()
        )
        existing_map = {row.chunk_index: row for row in existing}

        upserted: List[RagEmbeddingsIndex] = []
        for entry in entries:
            instance = existing_map.get(entry["chunk_index"])
            if instance:
                instance.qdrant_collection_name = entry["qdrant_collection_name"]
                instance.qdrant_point_id = entry["qdrant_point_id"]
                instance.vector_dim = entry["vector_dim"]
                instance.qdrant_vector_checksum = entry.get("qdrant_vector_checksum")
                instance.qdrant_payload_checksum = entry.get("qdrant_payload_checksum")
                upserted.append(instance)
                continue

            instance = RagEmbeddingsIndex(
                doc_content_id=_ensure_uuid(entry["doc_content_id"]),
                chunk_id=entry["chunk_id"],
                chunk_index=entry["chunk_index"],
                embedding_version=entry.get("embedding_version", "bge-m3-v1"),
                qdrant_collection_name=entry["qdrant_collection_name"],
                qdrant_point_id=entry["qdrant_point_id"],
                vector_dim=entry["vector_dim"],
                qdrant_vector_checksum=entry.get("qdrant_vector_checksum"),
                qdrant_payload_checksum=entry.get("qdrant_payload_checksum"),
            )
            session.add(instance)
            upserted.append(instance)

        session.flush()
        return upserted

    @staticmethod
    def delete_by_doc_content(session: Session, doc_content_id: Union[str, UUID]) -> int:
        """문서 컨텐츠의 모든 임베딩 인덱스 삭제 (모든 버전), 삭제된 행 수 반환"""
        count = (
            session.query(RagEmbeddingsIndex)
            .filter(RagEmbeddingsIndex.doc_content_id == _ensure_uuid(doc_content_id))
            .delete(synchronize_session="fetch")
        )
        session.flush()
        return count

    @staticmethod
    def delete_by_doc_content_and_version(
        session: Session,
        doc_content_id: Union[str, UUID],
        embedding_version: str,
    ) -> int:
        """특정 embedding_version의 인덱스만 삭제 (다른 버전 보존)"""
        count = (
            session.query(RagEmbeddingsIndex)
            .filter(
                RagEmbeddingsIndex.doc_content_id == _ensure_uuid(doc_content_id),
                RagEmbeddingsIndex.embedding_version == embedding_version,
            )
            .delete(synchronize_session="fetch")
        )
        session.flush()
        return count

    @staticmethod
    def list_versions_by_doc(
        session: Session,
        doc_content_id: Union[str, UUID],
    ) -> List[str]:
        """해당 doc에 이미 임베딩된 embedding_version 목록"""
        rows = (
            session.query(RagEmbeddingsIndex.embedding_version)
            .filter(RagEmbeddingsIndex.doc_content_id == _ensure_uuid(doc_content_id))
            .distinct()
            .all()
        )
        return [row[0] for row in rows]


class StorageObjectRepository:
    """MinIO 객체 메타 Repository"""

    @staticmethod
    def get_raw_by_doc_content_id(
        session: Session,
        doc_content_id: Union[str, UUID],
    ) -> Optional[StorageObjectFile]:
        """doc_content_id로 원본(raw) 파일의 StorageObjectFile 조회"""
        return (
            session.query(StorageObjectFile)
            .filter(
                StorageObjectFile.doc_content_id == _ensure_uuid(doc_content_id),
                StorageObjectFile.kind == ObjectKind.RAW.value,
            )
            .first()
        )

    @staticmethod
    def create(
        session: Session,
        *,
        doc_content_id: Optional[Union[str, UUID]],
        kind: ObjectKind,
        bucket: str,
        object_key: str,
        size_bytes: Optional[int],
        content_type: Optional[str],
        sha256: Optional[str] = None,
        etag: Optional[str] = None,
        created_by: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StorageObjectFile:
        doc_content_uuid = _ensure_uuid(doc_content_id) if doc_content_id else None
        kind_value = kind.value if isinstance(kind, ObjectKind) else str(kind)

        existing = (
            session.query(StorageObjectFile)
            .filter(
                StorageObjectFile.bucket == bucket,
                StorageObjectFile.object_key == object_key,
            )
            .one_or_none()
        )
        if existing:
            # Update the existing record to make operation idempotent
            existing.doc_content_id = doc_content_uuid
            existing.kind = kind_value
            existing.size_bytes = size_bytes
            existing.content_type = content_type
            existing.sha256 = sha256
            existing.etag = etag
            existing.created_by = created_by
            existing.metadata_json = metadata or {}
            session.flush()
            return existing

        record = StorageObjectFile(
            doc_content_id=doc_content_uuid,
            kind=kind_value,
            bucket=bucket,
            object_key=object_key,
            size_bytes=size_bytes,
            content_type=content_type,
            sha256=sha256,
            etag=etag,
            created_by=created_by,
            metadata_json=metadata or {},
        )
        session.add(record)
        session.flush()
        return record

    @staticmethod
    def create_many(
        session: Session,
        *,
        objects: Sequence[Dict[str, Any]],
    ) -> List[StorageObjectFile]:
        if not objects:
            return []

        # Preload existing records for the same bucket/object_key to reduce queries
        keys = {(obj["bucket"], obj["object_key"]) for obj in objects}
        existing = (
            session.query(StorageObjectFile)
            .filter(
                StorageObjectFile.bucket.in_({k[0] for k in keys}),
            )
            .all()
        )
        existing_map = {(row.bucket, row.object_key): row for row in existing}

        created: List[StorageObjectFile] = []
        for obj in objects:
            key = (obj["bucket"], obj["object_key"])
            instance = existing_map.get(key)
            if instance:
                instance.doc_content_id = _ensure_uuid(obj["doc_content_id"]) if obj.get("doc_content_id") else None
                instance.kind = obj["kind"].value if isinstance(obj["kind"], ObjectKind) else str(obj["kind"])
                instance.size_bytes = obj.get("size_bytes")
                instance.content_type = obj.get("content_type")
                instance.sha256 = obj.get("sha256")
                instance.etag = obj.get("etag")
                instance.created_by = obj.get("created_by")
                instance.metadata_json = obj.get("metadata") or {}
                created.append(instance)
                continue

            created.append(
                StorageObjectRepository.create(
                    session,
                    doc_content_id=obj.get("doc_content_id"),
                    kind=obj["kind"],
                    bucket=obj["bucket"],
                    object_key=obj["object_key"],
                    size_bytes=obj.get("size_bytes"),
                    content_type=obj.get("content_type"),
                    sha256=obj.get("sha256"),
                    etag=obj.get("etag"),
                    created_by=obj.get("created_by"),
                    metadata=obj.get("metadata"),
                )
            )
        session.flush()
        return created


class SimilarityCheckRepository:
    """유사도 검증 결과 Repository"""

    @staticmethod
    def create(
        session: Session,
        doc_content_id: Union[str, UUID],
        job_id: Optional[Union[str, UUID]],
        sample_count: int,
        high_similarity_matches: int,
        similarity_threshold: float,
        match_ratio: float,
        avg_similarity: float = 0.0,
        similar_documents: Optional[List] = None,
        details: Optional[Dict] = None,
        memo: Optional[str] = None,
    ) -> RagSimilarityCheck:
        """유사도 검증 결과 생성"""
        check = RagSimilarityCheck(
            doc_content_id=_ensure_uuid(doc_content_id),
            job_id=_ensure_uuid(job_id) if job_id else None,
            sample_count=sample_count,
            high_similarity_matches=high_similarity_matches,
            similarity_threshold=similarity_threshold,
            match_ratio=match_ratio,
            avg_similarity=avg_similarity,
            similar_documents=similar_documents or [],
            details=details or {},
            memo=memo,
        )
        session.add(check)
        session.flush()
        return check

    @staticmethod
    def get_by_doc_content(
        session: Session, doc_content_id: Union[str, UUID]
    ) -> Optional[RagSimilarityCheck]:
        """문서 컨텐츠로 유사도 검증 결과 조회 (최신 것)"""
        return (
            session.query(RagSimilarityCheck)
            .filter(RagSimilarityCheck.doc_content_id == _ensure_uuid(doc_content_id))
            .order_by(RagSimilarityCheck.created_at.desc())
            .first()
        )
