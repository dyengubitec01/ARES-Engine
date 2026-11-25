"""EW (Embedding Worker) 메인 워커"""
import hashlib
import json
import logging
import os
import socket
import tempfile
import time
from pathlib import Path
from typing import Optional
from uuid import NAMESPACE_DNS, uuid5, UUID


class PermanentFailureError(Exception):
    """재시도해도 성공할 수 없는 영구 실패 (예: 텍스트 추출 불가 PDF)"""
    pass

from config import settings
from kafka_client.consumer import KafkaConsumerWrapper
from kafka_client.producer import KafkaProducer
from db.connection import get_db_session
from db.repositories import (
    ChunkRepository,
    DocumentContentRepository,
    EmbeddingJobRepository,
    EmbeddingsIndexRepository,
    ProcessingStatsRepository,
    SimilarityCheckRepository,
    StatusEventRepository,
    StorageObjectRepository,
    UpsertHistoryRepository,
)
from models.job import JobPayload
from models.enums import DocumentStatus, JobStatus, ObjectKind, EventSource, StatusEventType
from storage.minio_client import MinIOClient
from storage.qdrant_client import QdrantClient, DENSE_VECTOR_NAME
from chunking import (
    extract_pdf_pages,
    extract_pdf_pages_with_ocr,
    extract_docx_pages,
    extract_doc_pages,
    extract_xlsx_rows,
    extract_xls_rows,
    extract_csv_rows,
    extract_pptx_pages,
    extract_ppt_pages,
    extract_hwp_pages,
    extract_hwpx_pages,
    extract_text_txt,
    chunk_by_sentences_with_page,
    chunk_by_sentences_with_page_estimated,
    chunk_by_rows_with_meta,
)
from chunking.parent_grouping import assign_parent_ids, PARENT_VERSION
from sqlalchemy.orm.attributes import flag_modified
from embeddings import BGEM3Client
from embeddings.bge_m3_client import BGEM3HybridClient
from embeddings.nemotron_ocr_client import NemotronOCRClient
from utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


def make_point_id(doc_content_id: str, chunk_index: int) -> str:
    """doc_content_id와 chunk_index로 UUID v5 point ID 생성"""
    raw = f"{doc_content_id}_{chunk_index}"
    return str(uuid5(NAMESPACE_DNS, raw))


def _estimate_token_count(text: str) -> int:
    """간단한 토큰 수 추정"""
    if not text:
        return 0
    char_based = max(1, len(text) // 4)
    word_based = len(text.split())
    return max(1, min(char_based, word_based or char_based))


def _convert_uuids_to_str(obj):
    """재귀적으로 모든 UUID를 문자열로 변환"""
    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: _convert_uuids_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_uuids_to_str(item) for item in obj]
    else:
        return obj


class EmbeddingWorker:
    """임베딩 워커"""
    
    def __init__(self):
        logger.info(f"임베딩 워커 초기화 시작: worker_id={os.getenv('WORKER_ID', 'worker-1')}")
        logger.info(f"Kafka 설정: topic={settings.kafka_request_topic}, group_id={settings.kafka_consumer_group}")
        
        self.consumer = KafkaConsumerWrapper(
            topic=settings.kafka_request_topic,
            group_id=settings.kafka_consumer_group
        )
        logger.info("Kafka Consumer 초기화 완료")
        
        self.kafka_producer = KafkaProducer()
        logger.info("Kafka Producer 초기화 완료")
        
        self.minio_client = MinIOClient()
        logger.info("MinIO Client 초기화 완료")
        
        self.qdrant_client = QdrantClient()
        logger.info("Qdrant Client 초기화 완료")
        
        self.embedding_client = BGEM3Client()
        logger.info("Embedding Client 초기화 완료")

        # 하이브리드 클라이언트 (lazy 초기화: 첫 하이브리드 요청 시 생성)
        self._hybrid_embedding_client = None
        self._hybrid_qdrant_client = None

        # OCR 클라이언트 (lazy 초기화: 첫 enable_ocr 요청 시 생성)
        self._ocr_client = None

        self.worker_id = os.getenv("WORKER_ID", socket.gethostname())
        logger.info(f"임베딩 워커 초기화 완료: worker_id={self.worker_id}")

    def _ensure_hybrid_clients(self):
        """하이브리드 클라이언트를 lazy 초기화"""
        if self._hybrid_embedding_client is None:
            self._hybrid_embedding_client = BGEM3HybridClient()
            logger.info("하이브리드 Embedding Client 초기화 완료")
        if self._hybrid_qdrant_client is None:
            self._hybrid_qdrant_client = QdrantClient(
                collection_name=settings.qdrant_collection_hybrid,
                hybrid=True,
            )
            logger.info("하이브리드 Qdrant Client 초기화 완료")

    def _ensure_ocr_client(self):
        """OCR 클라이언트 lazy 초기화 — 무조건 Nemotron OCR v2.

        다른 OCR(Gemma/Tesseract/PaddleOCR 등) 사용 금지 정책. 환경변수 OCR_PROVIDER 무관.
        """
        if self._ocr_client is None:
            self._ocr_client = NemotronOCRClient()
            logger.info("Nemotron OCR Client 초기화 완료 (강제 — 다른 OCR 미허용)")
        return self._ocr_client
    
    def _perform_similarity_check(
        self,
        job_id_str: str,
        doc_content_id: UUID,
        chunk_records: list,
        embeddings: list,
        original_filename: str = "알 수 없음",
        qdrant_client=None,
        vector_name: str = None,
    ) -> Optional[dict]:
        """10개 샘플 청크로 유사도 검증"""
        qdrant = qdrant_client or self.qdrant_client
        try:
            sample_size = min(settings.duplicate_sample_size, len(chunk_records))
            if sample_size < 1:
                logger.warning("유사도 검증 스킵: 청크가 없음")
                return None
            
            # 일정한 간격으로 샘플 선정
            step = len(chunk_records) // sample_size if sample_size > 1 else 1
            sample_indices = [i * step for i in range(sample_size)]
            sample_indices = sample_indices[:sample_size]
            
            logger.info(
                "🔍 유사도 검증 시작: job_id=%s, 샘플 수=%d, 간격=%d, 현재 문서 ID=%s",
                job_id_str, sample_size, step, str(doc_content_id)[:8]
            )
            
            high_similarity_count = 0
            sample_details = []
            all_similarity_scores = []  # 모든 샘플의 최고 점수 수집
            similar_doc_ids = {}  # 유사 문서별 발견 횟수 집계
            
            logger.info(
                "제목 : [%s] / 내용 : %s (ID: %s)",
                original_filename,
                chunk_records[0]["text"][:100] if chunk_records else "N/A",
                str(doc_content_id)[:12]
            )
            
            for idx in sample_indices:
                chunk = chunk_records[idx]
                vector = embeddings[idx]
                
                # Qdrant 검색 (본인 제외, 상위 10개로 확대)
                search_results = qdrant.search(
                    query_vector=vector,
                    limit=11,  # 본인 포함 11개
                    score_threshold=0.0,
                    vector_name=vector_name,
                )
                
                # 본인 제외
                similar_docs = [
                    r for r in search_results
                    if r.get("payload", {}).get("doc_content_id") != str(doc_content_id)
                ][:10]
                
                # 고유사도 문서 수 (threshold 이상)
                high_sim_docs = [
                    r for r in similar_docs
                    if r.get("score", 0) >= settings.duplicate_similarity_threshold
                ]
                
                # 유사 문서별 발견 횟수 집계
                for doc in high_sim_docs:
                    doc_id = doc.get("payload", {}).get("doc_content_id")
                    if doc_id:
                        if doc_id not in similar_doc_ids:
                            similar_doc_ids[doc_id] = {
                                "count": 0,
                                "filename": doc.get("payload", {}).get("original_filename"),
                                "max_score": 0.0,
                                "scores": []
                            }
                        similar_doc_ids[doc_id]["count"] += 1
                        similar_doc_ids[doc_id]["scores"].append(doc.get("score", 0))
                        similar_doc_ids[doc_id]["max_score"] = max(
                            similar_doc_ids[doc_id]["max_score"],
                            doc.get("score", 0)
                        )
                
                if high_sim_docs:
                    high_similarity_count += 1
                
                # 최고 점수 저장 (평균 계산용)
                if similar_docs:
                    top_score = similar_docs[0].get("score", 0)
                    all_similarity_scores.append(top_score)
                
                payload = similar_docs[0].get("payload", {}) if similar_docs else {}
                detail = {
                    "chunk_index": chunk["chunk_index"],
                    "chunk_id": chunk["id"],
                    "text_preview": chunk["text"][:100],
                    "similar_count": len(similar_docs),
                    "high_similarity_count": len(high_sim_docs),
                    "top_matches": [
                        {
                            "doc_content_id": doc.get("payload", {}).get("doc_content_id"),
                            "filename": doc.get("payload", {}).get("original_filename"),
                            "score": doc.get("score", 0),
                        }
                        for doc in high_sim_docs[:3]  # 상위 3개만
                    ] if high_sim_docs else [],
                    "top_match": {
                        "doc_content_id": payload.get("doc_content_id"),
                        "filename": payload.get("original_filename"),
                        "score": similar_docs[0].get("score", 0),
                    } if similar_docs else None,
                }
                sample_details.append(detail)
                
                # 고유사도 문서의 doc_content_id 목록 (디버깅용)
                high_sim_doc_ids = [
                    doc.get("payload", {}).get("doc_content_id", "unknown")[:8]
                    for doc in high_sim_docs
                ]
                
                # 각 샘플별 상세 로그는 너무 많으므로 주석 처리
                # logger.info(
                #     "  샘플 %d/%d (청크 %d): 검색 후보 %d개, 고유사도(%.0f%%↑) %d개, 최고점수 %.3f",
                #     sample_indices.index(idx) + 1,
                #     sample_size,
                #     chunk["chunk_index"],
                #     len(similar_docs),
                #     settings.duplicate_similarity_threshold * 100,
                #     len(high_sim_docs),
                #     similar_docs[0].get("score", 0) if similar_docs else 0.0
                # )
                # if high_sim_docs and len(high_sim_docs) <= 3:
                #     # 고유사도 문서가 3개 이하일 때만 ID 출력
                #     logger.info(
                #         "    └─ 고유사도 문서 ID: %s",
                #         ", ".join(high_sim_doc_ids)
                #     )
            
            match_ratio = high_similarity_count / sample_size if sample_size > 0 else 0.0
            
            # 평균 유사도 계산
            avg_similarity = (sum(all_similarity_scores) / len(all_similarity_scores) 
                            if all_similarity_scores else 0.0)
            
            # 유사 문서 목록 생성 (최고 점수 기준 정렬)
            similar_docs_list = sorted(
                similar_doc_ids.items(),
                key=lambda x: x[1]["max_score"],
                reverse=True
            )
            
            # 유니크 문서 개수 확인
            unique_doc_count = len(similar_docs_list)
            # logger.info(
            #     "📊 유니크 유사 문서 발견: %d개 (현재 문서 ID: %s 제외)",
            #     unique_doc_count,
            #     str(doc_content_id)[:12]
            # )
            
            # 평균 유사도 로그
            logger.info("=" * 80)
            logger.info(
                "📊 유사도 검증 완료: 평균 유사도 %.2f%%, 유사 문서 %d개 발견",
                avg_similarity * 100,
                unique_doc_count
            )
            logger.info("=" * 80)
            
            # 유사 문서별 상세 로그
            if similar_docs_list:
                logger.info("📋 유사 문서 목록 (유사도 높은 순):")
                for idx, (doc_id, info) in enumerate(similar_docs_list, 1):
                    avg_doc_score = sum(info["scores"]) / len(info["scores"]) if info["scores"] else 0.0
                    logger.info("")
                    logger.info(
                        "  %d. %s",
                        idx,
                        info["filename"] or "알 수 없음"
                    )
                    logger.info(
                        "     문서 ID: %s",
                        doc_id[:16]
                    )
                    logger.info(
                        "     유사도: 최고 %.2f%%, 평균 %.2f%% (샘플 %d/%d회 발견)",
                        info["max_score"] * 100,
                        avg_doc_score * 100,
                        info["count"],
                        sample_size
                    )
                logger.info("")
                logger.info("=" * 80)
            else:
                logger.info("✅ 유사 문서 없음 (신규 문서로 판단)")
                logger.info("=" * 80)
            
            memo = (
                f"평균 유사도 {avg_similarity:.2%}. "
                f"샘플 {sample_size}개 중 {high_similarity_count}개 청크에서 "
                f"유사도 {settings.duplicate_similarity_threshold:.0%} 이상의 문서 {len(similar_docs_list)}개 발견. "
                f"매칭 비율: {match_ratio:.1%}"
            )
            
            is_duplicate_risk = match_ratio >= settings.duplicate_match_ratio
            if is_duplicate_risk:
                memo += f" ⚠️ 중복 가능성 높음"
                logger.warning(memo)
            else:
                logger.info(memo)
            
            return {
                "sample_count": sample_size,
                "high_similarity_matches": high_similarity_count,
                "similarity_threshold": settings.duplicate_similarity_threshold,
                "match_ratio": match_ratio,
                "avg_similarity": avg_similarity,
                "similar_documents": [
                    {
                        "doc_content_id": doc_id,
                        "filename": info["filename"],
                        "match_count": info["count"],
                        "max_score": info["max_score"],
                        "avg_score": sum(info["scores"]) / len(info["scores"]) if info["scores"] else 0.0,
                    }
                    for doc_id, info in similar_docs_list
                ],
                "details": sample_details,
                "memo": memo,
                "is_duplicate_risk": is_duplicate_risk,
            }
            
        except Exception as e:
            logger.error("유사도 검증 실패: %s", e, exc_info=True)
            return None
    
    def process_job(self, job_payload: dict):
        """Job 처리"""
        payload = None
        tmp_path = None
        chunk_records = []
        job_id_str: Optional[str] = None
        doc_id: Optional[int] = None
        doc_language: Optional[str] = None

        try:
            logger.info(f"수신된 메시지 내용: {job_payload}")
            try:
                payload = JobPayload(**job_payload)
            except Exception as validation_error:
                logger.warning(f"JobPayload 검증 실패 (테스트 메시지 스킵): {type(validation_error).__name__}")
                # validation 실패한 메시지는 스킵하고 성공으로 처리 (커밋되도록)
                return True

            job_id_str = str(payload.job_id)
            doc_content_uuid = UUID(str(payload.doc_content_id))
            doc_content_id_str = str(doc_content_uuid)

            # 하이브리드 모드 판별
            is_hybrid = payload.embedding_profile == settings.embedding_profile_hybrid
            if is_hybrid:
                self._ensure_hybrid_clients()
                active_embedding_version = settings.embedding_version_hybrid
                active_qdrant = self._hybrid_qdrant_client
            else:
                active_embedding_version = settings.embedding_version
                active_qdrant = self.qdrant_client

            # 처리 방식 판별: re_chunk(추출+청킹부터) | re_vectorize(기존 청크 재활용)
            embedding_mode = getattr(payload, "embedding_mode", "re_chunk") or "re_chunk"
            is_re_vectorize = (embedding_mode == "re_vectorize")
            enable_ocr = bool(getattr(payload, "enable_ocr", False))

            logger.info(
                "Job 처리 시작: job_id=%s, doc_content_id=%s, embedding_profile=%s, mode=%s, ocr=%s",
                job_id_str,
                doc_content_id_str,
                payload.embedding_profile,
                embedding_mode,
                enable_ocr,
            )

            with get_db_session() as session:
                # Job이 DB에 존재하는지 먼저 확인 (워커 중단 등으로 job 레코드가 없을 수 있음)
                job_exists = EmbeddingJobRepository.get_by_id(session, payload.job_id)
                if not job_exists:
                    logger.warning(
                        "Job이 DB에 존재하지 않습니다 (중단된 작업으로 추정), 메시지 스킵: "
                        f"job_id={job_id_str}, doc_content_id={doc_content_id_str}"
                    )
                    return

                doc_content = DocumentContentRepository.get_by_id(
                    session, doc_content_uuid
                )
                if not doc_content:
                    raise ValueError(f"문서 컨텐츠를 찾을 수 없습니다: {doc_content_id_str}")

                # 이미 성공 처리된 문서는 스킵 (idempotent)
                # 단, 재임베딩 요청인 경우에는 스킵하지 않음
                is_re_embedding = payload.re_embedding
                existing_stats = ProcessingStatsRepository.get_by_doc_content(
                    session, doc_content_uuid
                )
                if not is_re_embedding and existing_stats and existing_stats.success_chunks > 0 and existing_stats.failed_chunks == 0:
                    logger.info(
                        "이미 임베딩 완료된 문서이므로 스킵합니다: doc_content_id=%s",
                        doc_content_id_str,
                    )
                    StatusEventRepository.record(
                        session,
                        doc_content_id=doc_content_uuid,
                        job_id=payload.job_id,
                        status=StatusEventType.SKIPPED.value,
                        source=EventSource.EW.value,
                        message="이미 임베딩 완료된 문서로 처리 스킵",
                        metadata={"worker_id": self.worker_id},
                    )
                    return

                if is_re_embedding:
                    logger.info(
                        "재임베딩 요청 처리: doc_content_id=%s, reason=%s",
                        doc_content_id_str,
                        payload.re_embedding_reason or "사유 없음",
                    )

                doc_id = doc_content.document_id
                doc_language = doc_content.language
                file_modified_at = doc_content.file_modified_at
                uploader_id = doc_content.uploader_id

                if not EmbeddingJobRepository.update_status(
                    session,
                    payload.job_id,
                    JobStatus.STARTED,
                    worker_id=self.worker_id,
                ):
                    raise ValueError(f"Job 상태 업데이트 실패: {job_id_str}")

                DocumentContentRepository.update_status(
                    session, doc_content_uuid, DocumentStatus.PARSING
                )
                StatusEventRepository.record(
                    session,
                    doc_content_id=doc_content_uuid,
                    job_id=payload.job_id,
                    status=StatusEventType.STARTED.value,
                    source=EventSource.EW.value,
                    message="임베딩 워커 처리 시작",
                    metadata={"worker_id": self.worker_id},
                )

            # Mode B (re_vectorize): 기존 청크 재활용 — 파일 다운로드/추출/청킹 모두 스킵
            existing_chunk_payloads = None
            if is_re_vectorize:
                with get_db_session() as session:
                    existing_rows = ChunkRepository.get_by_doc_content(session, doc_content_uuid)
                    if not existing_rows:
                        raise PermanentFailureError(
                            "re_vectorize 모드인데 기존 청크가 없습니다. re_chunk 모드로 재시도하세요."
                        )
                    existing_chunk_payloads = [
                        {
                            "id": str(c.id),
                            "doc_content_id": str(c.doc_content_id),
                            "chunk_index": c.chunk_index,
                            "extraction_version": c.extraction_version,
                            "text": c.text,
                            "token_count": c.token_count,
                            "text_checksum": c.text_checksum,
                            "text_hash": c.text_hash or c.text_checksum,
                            "page_start": c.page_start,
                            "page_end": c.page_end,
                            "sheet_name": c.sheet_name,
                            "row_start": c.row_start,
                            "row_end": c.row_end,
                            "metadata_json": c.metadata_json,
                        }
                        for c in existing_rows
                    ]
                logger.info(
                    "re_vectorize: 기존 청크 %d건 재활용 (다운로드/추출 스킵): doc_content_id=%s",
                    len(existing_chunk_payloads), doc_content_id_str,
                )
                chunk_inputs = [
                    {
                        "chunk_index": d["chunk_index"],
                        "embedding_version": active_embedding_version,
                        "extraction_version": d["extraction_version"],
                        "text": d["text"],
                        "token_count": d["token_count"],
                        "text_checksum": d["text_checksum"],
                        "text_hash": d["text_hash"],
                        "page_start": d["page_start"],
                        "page_end": d["page_end"],
                        "sheet_name": d["sheet_name"],
                        "row_start": d["row_start"],
                        "row_end": d["row_end"],
                        "metadata": d["metadata_json"],
                    }
                    for d in existing_chunk_payloads
                ]
            else:
                # Mode A (re_chunk): 파일 다운로드 + 추출 + 청킹
                file_data = self.minio_client.download_object(
                    payload.minio_bucket, payload.minio_object_key
                )
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=Path(payload.original_filename).suffix
                ) as tmp_file:
                    tmp_file.write(file_data)
                    tmp_path = tmp_file.name

                chunks = self._extract_and_chunk(
                    tmp_path,
                    payload.mime_type,
                    enable_ocr=getattr(payload, "enable_ocr", False),
                )
                if not chunks:
                    raise PermanentFailureError("텍스트를 추출할 수 없는 문서입니다. 텍스트가 이미지 또는 벡터 형태로 포함되어 있을 수 있습니다.")

                chunk_inputs = []
                for idx, chunk in enumerate(chunks):
                    chunk_text = (chunk.get("text") or "").strip()
                    if not chunk_text:
                        continue
                    chunk_index = chunk.get("chunk_index", idx)
                    text_checksum = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
                    text_hash = text_checksum  # text_hash와 text_checksum은 동일한 값 사용
                    chunk_inputs.append(
                        {
                            "chunk_index": chunk_index,
                            "embedding_version": active_embedding_version,
                            "extraction_version": payload.extraction_version,
                            "text": chunk_text,
                            "token_count": _estimate_token_count(chunk_text),
                            "text_checksum": text_checksum,
                            "text_hash": text_hash,
                            "page_start": chunk.get("page_start"),
                            "page_end": chunk.get("page_end"),
                            "sheet_name": chunk.get("sheet_name") or chunk.get("sheet_start"),
                            "row_start": chunk.get("row_start"),
                            "row_end": chunk.get("row_end"),
                            "metadata": {
                                "extraction_version": payload.extraction_version,
                                "sentence_count": chunk.get("sentence_count"),
                                "row_count": chunk.get("row_count"),
                            },
                        }
                    )

                if not chunk_inputs:
                    raise ValueError("유효한 청크가 생성되지 않았습니다.")

            total_tokens = sum(chunk["token_count"] for chunk in chunk_inputs)
            chunk_inputs.sort(key=lambda c: c["chunk_index"])
            texts = [item["text"] for item in chunk_inputs]
            
            logger.info(
                "임베딩 시작: job_id=%s, 총 청크 수=%d, 총 토큰=%d, hybrid=%s",
                job_id_str, len(chunk_inputs), total_tokens, is_hybrid
            )
            embed_start = time.perf_counter()

            if is_hybrid:
                hybrid_results = self._hybrid_embedding_client.embed_texts(texts)
                dense_vectors = [r["dense"] for r in hybrid_results]
                sparse_vectors = [r["sparse"] for r in hybrid_results]
            else:
                dense_vectors = self.embedding_client.embed_texts(texts)
                sparse_vectors = None

            embed_ms = int((time.perf_counter() - embed_start) * 1000)
            logger.info(
                "임베딩 완료: job_id=%s, 소요시간=%dms, 평균=%dms/청크, hybrid=%s",
                job_id_str, embed_ms, embed_ms // len(chunk_inputs) if chunk_inputs else 0, is_hybrid
            )

            if len(dense_vectors) != len(chunk_inputs):
                raise ValueError("임베딩 결과 수가 청크 수와 일치하지 않습니다.")

            # 재임베딩의 경우, 새 데이터 삽입 직전에 기존 데이터 정리
            # (큐 대기 중에는 기존 검색 데이터 유지 → 검색 가용성 확보)
            # re_vectorize 모드는 기존 청크/Qdrant/Index를 보존해야 하므로 cleanup 스킵
            is_re_embedding = bool(getattr(payload, "re_embedding", False))
            if is_re_embedding and not is_re_vectorize:
                logger.info(
                    "재임베딩: 기존 데이터 정리 시작 (Qdrant + DB): doc_content_id=%s",
                    doc_content_uuid,
                )
                # Qdrant 포인트 삭제
                try:
                    active_qdrant.delete_by_doc_content_id(str(doc_content_uuid))
                    logger.info("재임베딩: Qdrant 포인트 삭제 완료: doc_content_id=%s", doc_content_uuid)
                except Exception as e:
                    logger.error("재임베딩: Qdrant 포인트 삭제 실패: %s", e)
                    raise

                # DB 데이터 정리 (FK 제약 순서: upsert_history → index → chunks → stats)
                with get_db_session() as cleanup_session:
                    deleted_uh = UpsertHistoryRepository.delete_by_doc_content(cleanup_session, doc_content_uuid)
                    deleted_idx = EmbeddingsIndexRepository.delete_by_doc_content(cleanup_session, doc_content_uuid)
                    deleted_ch = ChunkRepository.delete_by_doc_content(cleanup_session, doc_content_uuid)
                    deleted_st = ProcessingStatsRepository.delete_by_doc_content(cleanup_session, doc_content_uuid)
                logger.info(
                    "재임베딩: DB 정리 완료 (upsert_history=%d, index=%d, chunks=%d, stats=%d)",
                    deleted_uh, deleted_idx, deleted_ch, deleted_st,
                )

            if is_re_vectorize:
                # Mode B: 기존 청크 row 그대로 사용 (create_batch 스킵)
                chunk_records = [
                    {
                        "id": d["id"],
                        "doc_content_id": d["doc_content_id"],
                        "chunk_index": d["chunk_index"],
                        "text": d["text"],
                        "token_count": d["token_count"],
                        "page_start": d["page_start"],
                        "page_end": d["page_end"],
                        "sheet_name": d["sheet_name"],
                        "row_start": d["row_start"],
                        "row_end": d["row_end"],
                        "metadata": d["metadata_json"],
                    }
                    for d in existing_chunk_payloads
                ]
                with get_db_session() as session:
                    StatusEventRepository.record(
                        session,
                        doc_content_id=doc_content_uuid,
                        job_id=payload.job_id,
                        status=StatusEventType.CHUNKED.value,
                        source=EventSource.EW.value,
                        message="re_vectorize: 기존 청크 재활용",
                        metadata={"chunk_count": len(chunk_records), "mode": "re_vectorize"},
                    )
            else:
                with get_db_session() as session:
                    chunk_rows = ChunkRepository.create_batch(
                        session,
                        doc_content_id=doc_content_uuid,
                        chunk_inputs=chunk_inputs,
                    )
                    chunk_records = [
                        {
                            "id": str(chunk_row.id),
                            "doc_content_id": str(chunk_row.doc_content_id),
                            "chunk_index": chunk_row.chunk_index,
                            "text": chunk_row.text,
                            "token_count": chunk_row.token_count,
                            "page_start": chunk_row.page_start,
                            "page_end": chunk_row.page_end,
                            "sheet_name": chunk_row.sheet_name,
                            "row_start": chunk_row.row_start,
                            "row_end": chunk_row.row_end,
                            "metadata": chunk_row.metadata_json,
                        }
                        for chunk_row in chunk_rows
                    ]
                    StatusEventRepository.record(
                        session,
                        doc_content_id=doc_content_uuid,
                        job_id=payload.job_id,
                        status=StatusEventType.CHUNKED.value,
                        source=EventSource.EW.value,
                        message="청크 메타데이터 저장 완료",
                        metadata={"chunk_count": len(chunk_records)},
                    )

            with get_db_session() as session:
                EmbeddingJobRepository.update_status(
                    session,
                    payload.job_id,
                    JobStatus.EMBEDDING,
                )
                DocumentContentRepository.update_status(
                    session, doc_content_uuid, DocumentStatus.EMBEDDING
                )
                StatusEventRepository.record(
                    session,
                    doc_content_id=doc_content_uuid,
                    job_id=payload.job_id,
                    status=StatusEventType.EMBEDDING.value,
                    source=EventSource.EW.value,
                    message="임베딩 시작",
                    metadata={"chunk_count": len(chunk_records)},
                )

            points = []
            upsert_entries = []
            embeddings_index_entries = []
            chunk_json_lines = []
            embedding_json_lines = []

            vector_dim = len(dense_vectors[0]) if dense_vectors else 0
            qdrant_collection_name = active_qdrant.collection_name
            
            # 청크 메타데이터 준비
            chunks_metadata = {
                "doc_id": int(doc_id) if doc_id else None,
                "doc_content_id": str(doc_content_uuid),
                "embedding_version": active_embedding_version,
                "extraction_version": payload.extraction_version,
                "original_filename": str(payload.original_filename) if payload.original_filename else None,
                "mime_type": str(payload.mime_type) if payload.mime_type else None,
                "language": str(doc_language) if doc_language else None,
                "file_modified_at": file_modified_at.isoformat() if file_modified_at else None,
                "total_chunks": int(len(chunk_records)),
                "total_tokens": int(total_tokens),
                "is_active": "Y",
            }

            # parent-document: 인접 임베딩 유사도로 연속 청크를 parent로 묶음 (emb_adj, LLM·추가비용 0)
            # dense_vectors 와 chunk_records 는 동일 chunk_index 순서로 정렬되어 zip된다.
            parent_ids = assign_parent_ids(
                dense_vectors,
                [len(c["text"]) for c in chunk_records],
            )
            # parent 내 위치 플래그: 검색측 edge-detection(첫/마지막이면 인접 parent 회수)용.
            # 위치 기준: parent_ids 가 직전/직후와 다르면 그 parent의 첫/마지막 청크.
            n_chunks = len(parent_ids)
            is_first_list = [i == 0 or parent_ids[i] != parent_ids[i - 1] for i in range(n_chunks)]
            is_last_list = [i == n_chunks - 1 or parent_ids[i] != parent_ids[i + 1] for i in range(n_chunks)]
            # RDB 청크 metadata 에도 기록 (Qdrant payload·MinIO 아티팩트와 정합)
            # re_chunk(create_batch)·re_vectorize(기존 청크 재활용) 두 경로 모두 uniform 업데이트.
            cidx_to_parent = {chunk_records[i]["chunk_index"]: parent_ids[i] for i in range(n_chunks)}
            cidx_to_first = {chunk_records[i]["chunk_index"]: bool(is_first_list[i]) for i in range(n_chunks)}
            cidx_to_last = {chunk_records[i]["chunk_index"]: bool(is_last_list[i]) for i in range(n_chunks)}
            with get_db_session() as session:
                for row in ChunkRepository.get_by_doc_content(session, doc_content_uuid):
                    if row.chunk_index in cidx_to_parent:
                        md = dict(row.metadata_json or {})
                        md["parent_id"] = cidx_to_parent[row.chunk_index]
                        md["parent_version"] = PARENT_VERSION
                        md["is_first_in_parent"] = cidx_to_first[row.chunk_index]
                        md["is_last_in_parent"] = cidx_to_last[row.chunk_index]
                        row.metadata_json = md
                        flag_modified(row, "metadata_json")

            for idx, (chunk_record, dense_vector) in enumerate(zip(chunk_records, dense_vectors)):
                # 컨텍스트 증강: 문서 타입별 상세 위치 정보
                location_context = []
                if chunk_record["page_start"] is not None:
                    if chunk_record["page_end"] and chunk_record["page_end"] != chunk_record["page_start"]:
                        location_context.append(f"페이지 {chunk_record['page_start']}-{chunk_record['page_end']}")
                    else:
                        location_context.append(f"페이지 {chunk_record['page_start']}")
                
                if chunk_record["sheet_name"]:
                    location_context.append(f"시트 '{chunk_record['sheet_name']}'")
                
                if chunk_record["row_start"] is not None:
                    if chunk_record["row_end"] and chunk_record["row_end"] != chunk_record["row_start"]:
                        location_context.append(f"행 {chunk_record['row_start']}-{chunk_record['row_end']}")
                    else:
                        location_context.append(f"행 {chunk_record['row_start']}")
                
                location_str = ", ".join(location_context) if location_context else "위치 정보 없음"
                
                # 파일 확장자 추출
                file_ext = Path(payload.original_filename).suffix.lower() if payload.original_filename else ""
                
                chunk_payload = {
                    # 기본 식별 정보
                    "doc_id": doc_id,
                    "doc_content_id": doc_content_id_str,
                    "chunk_id": str(chunk_record["id"]),
                    "chunk_index": chunk_record["chunk_index"],
                    # parent-document: 같은 parent_id 청크들이 하나의 의미 단위(검색 시 통째 반환용)
                    "parent_id": parent_ids[idx],
                    "parent_version": PARENT_VERSION,
                    # 검색측 edge-detection용: parent 내 첫/마지막 청크 여부
                    "is_first_in_parent": bool(is_first_list[idx]),
                    "is_last_in_parent": bool(is_last_list[idx]),
                    "embedding_version": active_embedding_version,
                    "extraction_version": payload.extraction_version,

                    # 파일 메타데이터
                    "original_filename": payload.original_filename,
                    "file_extension": file_ext,
                    "mime_type": payload.mime_type,
                    "language": doc_language,
                    "file_modified_at": file_modified_at.isoformat() if file_modified_at else None,
                    
                    # 위치 정보 (원본)
                    "page_start": chunk_record["page_start"],
                    "page_end": chunk_record["page_end"],
                    "sheet_name": chunk_record["sheet_name"],
                    "row_start": chunk_record["row_start"],
                    "row_end": chunk_record["row_end"],
                    
                    # 컨텍스트 증강 정보
                    "location_context": location_str,  # "페이지 3-5, 시트 'Sheet1', 행 10-15"
                    
                    # 청크 통계
                    "token_count": chunk_record["token_count"],
                    "text_length": len(chunk_record["text"]),
                    
                    # 검색 최적화 필드
                    "text_for_search": f"{payload.original_filename} {chunk_record['text']}",
                    
                    # 권한 및 접근 제어
                    "auth_dept_id": str(payload.auth_dept_id),
                    "uploader_id": str(uploader_id),
                    
                    # 활성화 상태
                    "is_active": "Y",
                }
                # Ensure UUIDs are JSON serializable
                for key, value in list(chunk_payload.items()):
                    if isinstance(value, UUID):
                        chunk_payload[key] = str(value)
                payload_checksum = hashlib.sha256(
                    json.dumps(chunk_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest()
                vector_checksum = hashlib.sha256(
                    json.dumps(dense_vector, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                ).hexdigest()

                qdrant_point_id = make_point_id(doc_content_id_str, chunk_record["chunk_index"])
                if is_hybrid:
                    sv = sparse_vectors[idx]
                    points.append(active_qdrant.create_hybrid_point(
                        qdrant_point_id, dense_vector,
                        sv["indices"], sv["values"], chunk_payload,
                    ))
                else:
                    points.append(active_qdrant.create_point(qdrant_point_id, dense_vector, chunk_payload))

                embeddings_index_entries.append(
                    {
                        "doc_content_id": doc_content_uuid,
                        "chunk_id": str(chunk_record["id"]),
                        "chunk_index": chunk_record["chunk_index"],
                        "embedding_version": active_embedding_version,
                        "qdrant_collection_name": qdrant_collection_name,
                        "qdrant_point_id": qdrant_point_id,
                        "vector_dim": len(dense_vector),
                        "qdrant_vector_checksum": vector_checksum,
                        "qdrant_payload_checksum": payload_checksum,
                    }
                )
                upsert_entries.append(
                    {
                        "job_id": payload.job_id,
                        "doc_content_id": doc_content_uuid,
                        "chunk_id": str(chunk_record["id"]),
                        "chunk_index": chunk_record["chunk_index"],
                        "qdrant_collection_name": qdrant_collection_name,
                        "qdrant_point_id": qdrant_point_id,
                        "status": "success",
                        "vector_dim": len(dense_vector),
                    }
                )
                chunk_data = {
                    # 기본 식별 정보
                    "chunk_id": str(chunk_record["id"]),
                    "chunk_index": chunk_record["chunk_index"],
                    "doc_content_id": str(chunk_record["doc_content_id"]),
                    "doc_id": doc_id,
                    # parent-document (Qdrant·RDB와 동일 값)
                    "parent_id": parent_ids[idx],
                    "parent_version": PARENT_VERSION,
                    "is_first_in_parent": bool(is_first_list[idx]),
                    "is_last_in_parent": bool(is_last_list[idx]),

                    # 텍스트 및 통계
                    "text": chunk_record["text"],
                    "token_count": chunk_record["token_count"],
                    "text_length": len(chunk_record["text"]),
                    
                    # 파일 메타데이터
                    "original_filename": payload.original_filename,
                    "file_extension": file_ext,
                    "mime_type": payload.mime_type,
                    "language": doc_language,
                    "file_modified_at": file_modified_at.isoformat() if file_modified_at else None,
                    
                    # 위치 정보 (원본)
                    "page_start": chunk_record["page_start"],
                    "page_end": chunk_record["page_end"],
                    "sheet_name": chunk_record["sheet_name"],
                    "row_start": chunk_record["row_start"],
                    "row_end": chunk_record["row_end"],
                    
                    # 컨텍스트 증강 정보
                    "location_context": chunk_payload["location_context"],
                    
                    # 권한 및 접근 제어
                    "auth_dept_id": str(payload.auth_dept_id),
                    "uploader_id": str(uploader_id),
                    
                    # 기타 메타데이터
                    "metadata": chunk_record["metadata"],
                }
                # 모든 UUID를 문자열로 변환
                chunk_data = _convert_uuids_to_str(chunk_data)
                chunk_json_lines.append(json.dumps(chunk_data, ensure_ascii=False))
                embedding_data = {
                    # 기본 정보
                    "chunk_id": str(chunk_record["id"]),
                    "chunk_index": chunk_record["chunk_index"],
                    "doc_content_id": str(chunk_record["doc_content_id"]),

                    # 벡터 데이터
                    "vector": dense_vector,
                    "vector_dim": len(dense_vector),
                    
                    # 컨텍스트 정보 (검색 시 참고용)
                    "original_filename": payload.original_filename,
                    "location_context": chunk_payload["location_context"],
                    "file_modified_at": file_modified_at.isoformat() if file_modified_at else None,
                    
                    # 권한 및 접근 제어
                    "auth_dept_id": str(payload.auth_dept_id),
                    "uploader_id": str(uploader_id),
                }
                if is_hybrid:
                    embedding_data["sparse"] = sparse_vectors[idx]
                # 모든 UUID를 문자열로 변환
                embedding_data = _convert_uuids_to_str(embedding_data)
                embedding_json_lines.append(json.dumps(embedding_data, ensure_ascii=False))

            logger.info(
                "Qdrant 업서트 시작: job_id=%s, 포인트 수=%d, 컬렉션=%s",
                job_id_str, len(points), qdrant_collection_name
            )
            active_qdrant.upsert_points(points)
            logger.info("Qdrant 업서트 완료: job_id=%s", job_id_str)

            # 유사도 검증 수행 (하이브리드에서도 dense 벡터 기반으로 검증)
            similarity_result = self._perform_similarity_check(
                job_id_str, doc_content_uuid, chunk_records, dense_vectors,
                original_filename=payload.original_filename or "알 수 없음",
                qdrant_client=active_qdrant,
                vector_name=DENSE_VECTOR_NAME if is_hybrid else None,
            )

            chunk_bytes = "\n".join(chunk_json_lines).encode("utf-8")
            embedding_bytes = "\n".join(embedding_json_lines).encode("utf-8")
            
            # 청크 메타데이터 (metadata.json)
            chunks_metadata_bytes = json.dumps(chunks_metadata, ensure_ascii=False, indent=2).encode("utf-8")
            
            # 임베딩 통계 (stats.json)
            stats_payload = {
                "doc_id": int(doc_id) if doc_id else None,
                "doc_content_id": doc_content_id_str,
                "embedding_version": active_embedding_version,
                "extraction_version": payload.extraction_version,
                "model_name": settings.bge_m3_model_name,
                "model_version": active_embedding_version,
                "vector_dim": vector_dim,
                "total_chunks": len(chunk_records),
                "success_chunks": len(chunk_records),
                "failed_chunks": 0,
                "total_tokens": total_tokens,
                "embed_ms": embed_ms,
                "auth_dept_id": str(payload.auth_dept_id),
                "uploader_id": str(uploader_id),
                "is_active": "Y",
            }
            stats_bytes = json.dumps(stats_payload, ensure_ascii=False, indent=2).encode("utf-8")

            bucket = settings.minio_bucket
            document_id_str = str(doc_id)
            embedding_version = active_embedding_version
            chunks_key = f"chunks/{document_id_str}/{embedding_version}/chunks.jsonl"
            chunks_metadata_key = f"chunks/{document_id_str}/{embedding_version}/metadata.json"
            embeddings_key = f"embeddings/{document_id_str}/{embedding_version}/vectors.jsonl"
            stats_key = f"embeddings/{document_id_str}/{embedding_version}/stats.json"

            logger.info("MinIO 업로드 시작: job_id=%s, bucket=%s", job_id_str, bucket)
            
            # 청크 데이터 업로드
            self.minio_client.upload_object(
                bucket, chunks_key, chunk_bytes, content_type="application/jsonl"
            )
            logger.info("MinIO 청크 업로드 완료: %s (%d bytes)", chunks_key, len(chunk_bytes))
            
            # 청크 메타데이터 업로드
            self.minio_client.upload_object(
                bucket, chunks_metadata_key, chunks_metadata_bytes, content_type="application/json"
            )
            logger.info("MinIO 청크 메타데이터 업로드 완료: %s (%d bytes)", chunks_metadata_key, len(chunks_metadata_bytes))
            
            # 임베딩 벡터 업로드
            self.minio_client.upload_object(
                bucket, embeddings_key, embedding_bytes, content_type="application/jsonl"
            )
            logger.info("MinIO 임베딩 업로드 완료: %s (%d bytes)", embeddings_key, len(embedding_bytes))
            
            # 임베딩 통계 업로드
            self.minio_client.upload_object(
                bucket, stats_key, stats_bytes, content_type="application/json"
            )
            logger.info("MinIO 통계 업로드 완료: %s", stats_key)

            storage_entries = []
            for key, data_bytes, kind, content_type in [
                (
                    chunks_key,
                    chunk_bytes,
                    ObjectKind.CHUNKS,
                    "application/jsonl",
                ),
                (
                    chunks_metadata_key,
                    chunks_metadata_bytes,
                    ObjectKind.CHUNKS_METADATA,
                    "application/json",
                ),
                (
                    embeddings_key,
                    embedding_bytes,
                    ObjectKind.EMBEDDING,
                    "application/jsonl",
                ),
                (
                    stats_key,
                    stats_bytes,
                    ObjectKind.STATS,
                    "application/json",
                ),
            ]:
                metadata = self.minio_client.get_object_metadata(bucket, key) or {}
                storage_entries.append(
                    {
                        "doc_content_id": doc_content_uuid,
                        "kind": kind,
                        "bucket": bucket,
                        "object_key": key,
                        "size_bytes": len(data_bytes),
                        "content_type": content_type,
                        "sha256": hashlib.sha256(data_bytes).hexdigest(),
                        "etag": metadata.get("etag"),
                        "metadata": {
                            "chunk_count": len(chunk_records),
                            "total_tokens": total_tokens,
                            "file_modified_at": file_modified_at.isoformat() if file_modified_at else None,
                            "original_filename": payload.original_filename,
                            "mime_type": payload.mime_type,
                        },
                    }
                )

            logger.info("RDB 메타데이터 저장 시작: job_id=%s", job_id_str)
            with get_db_session() as session:
                UpsertHistoryRepository.create_batch(session, upsert_entries)
                logger.info("업서트 히스토리 저장 완료: %d건", len(upsert_entries))
                
                EmbeddingsIndexRepository.upsert_many(session, embeddings_index_entries)
                logger.info("임베딩 인덱스 저장 완료: %d건", len(embeddings_index_entries))
                
                # ProcessingStatsRepository.upsert()에 필요한 파라미터만 전달
                stats_for_db = {
                    "doc_content_id": stats_payload["doc_content_id"],
                    "model_name": stats_payload["model_name"],
                    "model_version": stats_payload["model_version"],
                    "vector_dim": stats_payload["vector_dim"],
                    "total_chunks": stats_payload["total_chunks"],
                    "success_chunks": stats_payload["success_chunks"],
                    "failed_chunks": stats_payload["failed_chunks"],
                    "total_tokens": stats_payload["total_tokens"],
                    "embed_ms": stats_payload["embed_ms"],
                }
                ProcessingStatsRepository.upsert(session, **stats_for_db)
                logger.info("처리 통계 저장 완료")
                
                StorageObjectRepository.create_many(session, objects=storage_entries)
                logger.info("스토리지 객체 메타데이터 저장 완료: %d건", len(storage_entries))

                # 유사도 검증 결과 저장
                if similarity_result:
                    SimilarityCheckRepository.create(
                        session,
                        doc_content_id=doc_content_uuid,
                        job_id=payload.job_id,
                        **{k: v for k, v in similarity_result.items() 
                           if k not in ['is_duplicate_risk']}
                    )
                    logger.info("유사도 검증 결과 저장 완료")
                    
                    # 중복 위험 감지 시 이벤트 기록
                    if similarity_result.get("is_duplicate_risk"):
                        StatusEventRepository.record(
                            session,
                            doc_content_id=doc_content_uuid,
                            job_id=payload.job_id,
                            status="duplicate_risk_detected",
                            source=EventSource.EW.value,
                            message=f"⚠️ 중복 위험 감지: {similarity_result.get('memo')}",
                            metadata={
                                "avg_similarity": similarity_result.get("avg_similarity"),
                                "match_ratio": similarity_result.get("match_ratio"),
                                "similar_documents_count": len(similarity_result.get("similar_documents", [])),
                                "similar_documents": similarity_result.get("similar_documents", [])[:5],  # 최대 5개만
                            },
                        )
                        logger.warning("⚠️ 중복 위험 이벤트 기록 완료")
                    else:
                        # 중복 위험은 없지만 유사도 검증 완료 이벤트 기록
                        StatusEventRepository.record(
                            session,
                            doc_content_id=doc_content_uuid,
                            job_id=payload.job_id,
                            status="similarity_check_completed",
                            source=EventSource.EW.value,
                            message=f"유사도 검증 완료: 평균 {similarity_result.get('avg_similarity', 0):.1%}",
                            metadata={
                                "avg_similarity": similarity_result.get("avg_similarity"),
                                "match_ratio": similarity_result.get("match_ratio"),
                                "similar_documents_count": len(similarity_result.get("similar_documents", [])),
                            },
                        )

                StatusEventRepository.record(
                    session,
                    doc_content_id=doc_content_uuid,
                    job_id=payload.job_id,
                    status=StatusEventType.QDRANT_UPSERTED.value,
                    source=EventSource.EW.value,
                    message="Qdrant 업서트 완료",
                    metadata={"chunk_count": len(chunk_records)},
                )

                EmbeddingJobRepository.update_status(
                    session, payload.job_id, JobStatus.DONE, worker_id=self.worker_id
                )
                DocumentContentRepository.update_status(
                    session, doc_content_uuid, DocumentStatus.COMPLETED
                )
                StatusEventRepository.record(
                    session,
                    doc_content_id=doc_content_uuid,
                    job_id=payload.job_id,
                    status=StatusEventType.DONE.value,
                    source=EventSource.EW.value,
                    message="임베딩 처리 완료",
                    metadata={
                        "chunk_count": len(chunk_records),
                        "total_tokens": total_tokens,
                        "embed_ms": embed_ms,
                    },
                )

            self.kafka_producer.send_embedding_status(
                job_id=job_id_str,
                doc_content_id=doc_content_id_str,
                status="completed",
                message="임베딩 처리 완료",
                metadata={
                    "chunk_count": len(chunk_records),
                    "total_tokens": total_tokens,
                    "embed_ms": embed_ms,
                },
            )
            logger.info("Job 처리 완료: job_id=%s", job_id_str)

        except PermanentFailureError as e:
            # 재시도해도 성공할 수 없는 영구 실패 — 즉시 FAILED 처리
            logger.error("Job 영구 실패 (재시도 불가): job_id=%s, error=%s", job_id_str, e)
            if payload:
                try:
                    with get_db_session() as session:
                        EmbeddingJobRepository.update_status(
                            session,
                            payload.job_id,
                            JobStatus.FAILED,
                            worker_id=self.worker_id,
                            error_message=f"[영구 실패] {str(e)[:1900]}",
                        )
                        DocumentContentRepository.update_status(
                            session,
                            doc_content_uuid,
                            DocumentStatus.FAILED,
                            status_reason=str(e)[:400],
                            status_message="AI 지식 추가에 활용할 수 없는 유형의 문서입니다. 관리자에게 문의해주세요.",
                        )
                        StatusEventRepository.record(
                            session,
                            doc_content_id=doc_content_uuid,
                            job_id=payload.job_id,
                            status=StatusEventType.FAILED_PERMANENT.value,
                            source=EventSource.EW.value,
                            message=str(e)[:500],
                            metadata={"error": str(e)[:500]},
                        )
                    try:
                        self.kafka_producer.send_embedding_status(
                            job_id=job_id_str or str(payload.job_id),
                            doc_content_id=doc_content_id_str,
                            status="failed_permanent",
                            message=str(e)[:200],
                            metadata={"permanent": True},
                        )
                    except Exception as kafka_error:
                        logger.error("영구 실패 알림 전송 실패: %s", kafka_error)
                except Exception as update_error:
                    logger.error("영구 실패 처리 중 오류: %s", update_error)
            raise

        except Exception as e:
            logger.exception("Job 처리 실패: %s", e)
            if payload:
                try:
                    with get_db_session() as session:
                        # 재시도 카운트 증가
                        current_retry_count = EmbeddingJobRepository.increment_retry_count(
                            session, payload.job_id
                        )

                        max_retries = settings.job_max_retries

                        if current_retry_count >= max_retries:
                            # 최대 재시도 횟수 초과 - FAILED로 변경하고 더 이상 재시도하지 않음
                            logger.error(
                                "최대 재시도 횟수(%d) 초과 - Job을 FAILED로 처리: job_id=%s",
                                max_retries,
                                job_id_str,
                            )
                            EmbeddingJobRepository.update_status(
                                session,
                                payload.job_id,
                                JobStatus.FAILED,
                                worker_id=self.worker_id,
                                error_message=f"[재시도 {current_retry_count}회 실패] {str(e)[:1900]}",
                            )
                            DocumentContentRepository.update_status(
                                session,
                                doc_content_uuid,
                                DocumentStatus.FAILED,
                                status_reason=f"최대 재시도 횟수 초과: {str(e)[:400]}",
                                status_message="AI 지식 추가 도중 알 수 없는 원인으로 실패하였습니다. 재시도 해주세요.",
                            )
                            StatusEventRepository.record(
                                session,
                                doc_content_id=doc_content_uuid,
                                job_id=payload.job_id,
                                status=StatusEventType.FAILED_PERMANENT.value,
                                source=EventSource.EW.value,
                                message=f"최대 재시도 횟수({max_retries}회) 초과",
                                metadata={
                                    "error": str(e)[:500],
                                    "retry_count": current_retry_count,
                                },
                            )

                            # DLQ 토픽으로 알림 전송
                            try:
                                self.kafka_producer.send_embedding_status(
                                    job_id=job_id_str or str(payload.job_id),
                                    doc_content_id=doc_content_id_str,
                                    status="failed_permanent",
                                    message=f"최대 재시도 횟수({max_retries}회) 초과: {str(e)[:200]}",
                                    metadata={"retry_count": current_retry_count},
                                )
                            except Exception as kafka_error:
                                logger.error("DLQ 알림 전송 실패: %s", kafka_error)
                        else:
                            # 재시도 가능 - 커밋하지 않고 다시 시도
                            logger.warning(
                                "Job 처리 실패 (재시도 %d/%d): job_id=%s, error=%s",
                                current_retry_count,
                                max_retries,
                                job_id_str,
                                str(e)[:200],
                            )
                            StatusEventRepository.record(
                                session,
                                doc_content_id=doc_content_uuid,
                                job_id=payload.job_id,
                                status=StatusEventType.RETRY.value,
                                source=EventSource.EW.value,
                                message=f"재시도 {current_retry_count}/{max_retries}",
                                metadata={
                                    "error": str(e)[:500],
                                    "retry_count": current_retry_count,
                                },
                            )
                except Exception as update_error:
                    logger.error("재시도 로직 처리 실패: %s", update_error)
            raise

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return

    
    def _extract_and_chunk(self, file_path: str, mime_type: str, enable_ocr: bool = False) -> list:
        """파일 추출 및 청킹"""
        ext = Path(file_path).suffix.lower()

        # OCR 활성화 시 클라이언트와 OCR 키워드 인자 준비.
        # - pdf_ocr_kwargs: PDF 변환 경유 형식(.pdf/.docx/.doc/.ppt)에서 사용 — 페이지 단위 자동 판정 파라미터 포함
        # - simple_ocr_kwargs: 직접 처리 형식(.pptx/.xlsx/.hwp/.hwpx)에서 사용 — 이미지 단위 OCR만, upscale 파라미터만
        ocr_client = self._ensure_ocr_client() if enable_ocr else None
        pdf_ocr_kwargs = {}
        simple_ocr_kwargs = {}
        if ocr_client is not None:
            pdf_ocr_kwargs = {
                "ocr_client": ocr_client,
                "page_text_threshold": settings.ocr_page_text_threshold,
                "text_layer_corruption_gate": settings.ocr_text_layer_corruption_gate,
                "render_scale": settings.ocr_render_scale,
                "image_upscale_threshold_px": settings.ocr_image_upscale_threshold_px,
                "image_upscale_factor": settings.ocr_image_upscale_factor,
                "page_drawings_threshold": settings.ocr_page_drawings_threshold,
            }
            simple_ocr_kwargs = {
                "ocr_client": ocr_client,
                "image_upscale_threshold_px": settings.ocr_image_upscale_threshold_px,
                "image_upscale_factor": settings.ocr_image_upscale_factor,
            }

        if ext == ".pdf":
            if enable_ocr:
                # OCR 모드: 페이지 단위 자동 판정 (텍스트 추출 + 이미지별 OCR / 페이지 통째 OCR)
                pages = extract_pdf_pages_with_ocr(file_path, **pdf_ocr_kwargs)
                logger.info(f"PDF OCR 모드 추출 결과: {len(pages)} 페이지")
                if not pages:
                    raise PermanentFailureError("OCR 모드에서도 텍스트를 추출할 수 없는 PDF입니다.")
            else:
                pages = extract_pdf_pages(file_path)
                logger.info(f"PDF 추출 결과: {len(pages)} 페이지")

                # PDF 텍스트 추출 품질 검증
                # ToUnicode CMap이 없는 HWP→PDF 변환 문서 등에서
                # CID만 존재하고 유니코드 매핑이 없어 텍스트가 추출되지 않는 경우를 감지
                if len(pages) >= 3:
                    non_empty_pages = sum(
                        1 for _, text in pages
                        if len(text.strip()) >= 30
                    )
                    ratio = non_empty_pages / len(pages)
                    if ratio < 0.1:
                        raise PermanentFailureError(
                            f"PDF 텍스트 추출 실패: {len(pages)}페이지 중 "
                            f"유효 텍스트가 있는 페이지가 {non_empty_pages}개({ratio:.0%})뿐입니다. "
                            f"CID 매핑 누락(HWP→PDF 변환 문서 등)으로 인해 "
                            f"텍스트를 추출할 수 없는 PDF일 수 있습니다. "
                            f"OCR 처리가 필요합니다(enable_ocr=true)."
                        )

            return chunk_by_sentences_with_page(pages, chunk_size=800, overlap_sents=2, locator_type="page")

        elif ext == ".docx":
            # 페이지 정보를 정확히 얻을 수 없으므로 page_start/end=None 처리
            pages = extract_docx_pages(file_path, use_libreoffice=settings.use_libreoffice, **pdf_ocr_kwargs)
            return chunk_by_sentences_with_page_estimated(pages, locator_type="section", chunk_size=800, overlap_sents=2)

        elif ext == ".doc":
            # 페이지 정보를 정확히 얻을 수 없으므로 page_start/end=None 처리
            pages = extract_doc_pages(file_path, use_libreoffice=settings.use_libreoffice, **pdf_ocr_kwargs)
            return chunk_by_sentences_with_page_estimated(pages, locator_type="section", chunk_size=800, overlap_sents=2)

        elif ext in [".xlsx", ".xlsm", ".xls", ".csv"]:
            if ext in (".xlsx", ".xlsm"):
                rows = extract_xlsx_rows(file_path, **simple_ocr_kwargs)
            elif ext == ".xls":
                # .xls는 OLE 바이너리. 이미지 추출은 지원하지 않음 (텍스트만)
                rows = extract_xls_rows(file_path)
            else:
                # .csv는 이미지 없음
                rows = extract_csv_rows(file_path)
            return chunk_by_rows_with_meta(rows, chunk_size=800, overlap_rows=1)

        elif ext == ".pptx":
            pages = extract_pptx_pages(file_path, **simple_ocr_kwargs)
            return chunk_by_sentences_with_page(pages, chunk_size=800, overlap_sents=2, locator_type="page")

        elif ext == ".ppt":
            pages = extract_ppt_pages(file_path, **pdf_ocr_kwargs)
            return chunk_by_sentences_with_page(pages, chunk_size=800, overlap_sents=2, locator_type="page")

        elif ext == ".hwp":
            # 페이지 정보를 정확히 얻을 수 없으므로 page_start/end=None 처리 (추정값 무시)
            try:
                pages, _ = extract_hwp_pages(file_path, **simple_ocr_kwargs)
            except ValueError as e:
                raise PermanentFailureError(str(e)) from e
            return chunk_by_sentences_with_page_estimated(
                pages,
                locator_type="section",
                chunk_size=800,
                overlap_sents=2
            )

        elif ext == ".hwpx":
            # 페이지 정보를 정확히 얻을 수 없으므로 page_start/end=None 처리 (추정값 무시)
            try:
                pages, _ = extract_hwpx_pages(file_path, **simple_ocr_kwargs)
            except ValueError as e:
                raise PermanentFailureError(str(e)) from e
            return chunk_by_sentences_with_page_estimated(
                pages,
                locator_type="section",
                chunk_size=800,
                overlap_sents=2
            )
        
        elif ext == ".txt":
            # 페이지 정보를 얻을 수 없으므로 page_start/end=None 처리
            text = extract_text_txt(file_path)
            pages = [(1, text)]
            return chunk_by_sentences_with_page_estimated(pages, locator_type="section", chunk_size=800, overlap_sents=2)
        
        else:
            raise ValueError(f"지원하지 않는 파일 확장자: {ext}")
    
    def _should_commit_failed_job(self, job_id: str) -> bool:
        """실패한 Job을 커밋해야 하는지 확인 (최대 재시도 횟수 초과 시 커밋)"""
        try:
            with get_db_session() as session:
                job = EmbeddingJobRepository.get_by_id(session, job_id)
                if not job:
                    # Job이 없으면 커밋 (이상한 메시지)
                    return True
                
                # 최대 재시도 횟수 초과하면 커밋 (더 이상 재시도하지 않음)
                return job.retry_count >= settings.job_max_retries
        except Exception as e:
            logger.error("재시도 횟수 확인 실패: %s", e)
            # 오류 발생 시 커밋하지 않음 (안전한 쪽으로)
            return False

    def run(self):
        """워커 실행"""
        logger.info(f"임베딩 워커 시작: worker_id={self.worker_id}")
        from queue import Queue, Empty
        import threading
        from kafka.errors import KafkaError
        from kafka import TopicPartition
        
        task_queue: Queue = Queue()
        result_queue: Queue = Queue()
        stop_event = threading.Event()
        

        def worker_loop():
            while not stop_event.is_set():
                try:
                    rec = task_queue.get(timeout=0.5)
                except Empty:
                    continue
                success = False
                try:
                    self.process_job(rec.value)
                    success = True
                except PermanentFailureError as e:
                    # 재시도 불가 — 이미 FAILED 처리됨, 커밋하여 메시지 소비 완료
                    logger.error(f"영구 실패 (커밋 처리): topic={rec.topic}, partition={rec.partition}, offset={rec.offset}, error={e}")
                    success = True
                except Exception as e:
                    logger.exception(f"메시지 처리 실패: topic={rec.topic}, partition={rec.partition}, offset={rec.offset}, error={e}")
                finally:
                    result_queue.put((rec, success))
                    task_queue.task_done()

        worker_thread = threading.Thread(target=worker_loop, daemon=True)
        worker_thread.start()

        try:
            while not stop_event.is_set():
                # poll은 짧게, 처리는 워커 스레드에서 수행
                polled = self.consumer.poll(timeout_ms=500, max_records=1)
                # polled는 dict[TopicPartition, List[ConsumerRecord]]
                for records in polled.values():
                    for rec in records:
                        kafka_received_waiting = task_queue.qsize()
                        logger.info(
                            f"Kafka 메시지 수신: topic={rec.topic}, partition={rec.partition}, offset={rec.offset}, key={rec.key}, "
                            f"Kafka수신대기={kafka_received_waiting}개"
                        )
                        task_queue.put(rec)

                # 처리 완료 결과 확인 후 커밋
                while True:
                    try:
                        rec, success = result_queue.get_nowait()
                    except Empty:
                        break
                    if success:
                        try:
                            self.consumer.commit_offsets([rec])
                            # 내 파티션 잔여량
                            my_remaining = self.consumer.get_pending_count(last_record=rec)
                            # 전체 파티션(0,1,2) 잔여량
                            total_remaining = self.consumer.get_total_pending_count(last_record=rec)
                            
                            # 진행 상황 메시지
                            if total_remaining == 0:
                                status_msg = "✅ 모든 작업 완료"
                            else:
                                status_msg = f"⏳ 처리 진행 중"
                            
                            logger.info(
                                "커밋 완료: topic=%s partition=%s offset=%s, 전체 잔여=%d개 (내 파티션=%d개) | %s",
                                rec.topic, rec.partition, rec.offset, total_remaining, my_remaining, status_msg,
                            )
                        except KafkaError as e:
                            logger.error(f"커밋 실패: {e}")
                    else:
                        # 실패한 경우 - 재시도 횟수 확인 후 커밋 여부 결정
                        job_id = rec.value.get("job_id") if isinstance(rec.value, dict) else None
                        should_commit = self._should_commit_failed_job(job_id) if job_id else False
                        
                        if should_commit:
                            logger.warning(
                                "최대 재시도 횟수 초과 - 메시지 커밋: topic=%s partition=%s offset=%s job_id=%s",
                                rec.topic, rec.partition, rec.offset, job_id,
                            )
                            try:
                                self.consumer.commit_offsets([rec])
                            except KafkaError as e:
                                logger.error(f"커밋 실패: {e}")
                        else:
                            logger.warning(
                                "처리 실패 - 재시도를 위해 커밋하지 않음: topic=%s partition=%s offset=%s job_id=%s",
                                rec.topic, rec.partition, rec.offset, job_id,
                            )
                    result_queue.task_done()

        except KeyboardInterrupt:
            logger.info("워커 종료 요청")
        except Exception as e:
            logger.exception(f"워커 실행 중 에러: {e}")
        finally:
            stop_event.set()
            worker_thread.join(timeout=5)
            logger.info("워커 종료 중...")
            self.consumer.close()
            self.kafka_producer.close()
            logger.info("워커 종료 완료")


def main():
    """메인 함수"""
    worker_id = os.getenv('WORKER_ID', 'ew-1')

    setup_logging(
        service_name='EW',
        log_dir='logs',
        level=logging.INFO,
        console_output=True
    )

    # PyMuPDF의 stderr 직출력 메시지 차단 ("MuPDF error: unknown cid font type" 등).
    # OCR 폴백이 정상 작동하는 신호일 뿐이라 로그 노이즈만 됨.
    # Python logger 경로의 진짜 에러는 그대로 흐름.
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)

    worker = EmbeddingWorker()
    worker.run()


if __name__ == "__main__":
    main()

