"""
ER (Embedding Request Server) - 테스트 버전
FastAPI 기반 임베딩 요청 서버
"""
import logging
import json
import uuid
import itertools
import mimetypes
import os
import yaml
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Literal, Optional, Union
from uuid import UUID
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware  # CORS 미들웨어 추가
from pydantic import BaseModel, Field, model_validator
# config는 먼저 import (프로젝트 경로 필요)
from config import settings
from storage.minio_client import MinIOClient
from db.connection import get_db_session
from db.repositories import (
    ChunkRepository,
    DocumentContentRepository,
    EmbeddingJobRepository,
    StatusEventRepository,
    StorageObjectRepository,
)
from models.rdb_models import DocDocumentContent, RagEmbeddingJob
from models.enums import DocumentStatus, JobStatus, EventSource, StatusEventType
from utils.json_utils import to_jsonable
from embeddings.bge_m3_client import BGEM3Client, BGEM3HybridClient
from storage.qdrant_client import QdrantClient as QdrantVectorClient

# kafka-python 라이브러리 import (로컬 패키지 이름을 kafka_client로 변경하여 충돌 해결)
from kafka import KafkaProducer as KafkaProducerBase
from kafka.errors import KafkaError

# 로깅 설정 (파일 기반)
from utils.logging_config import setup_logging

setup_logging(
    service_name='ER',
    log_dir='logs',
    level=logging.INFO,
    console_output=True
)
logger = logging.getLogger(__name__)

# 모델 로딩 진행률 표시 완전 제거
os.environ['TQDM_DISABLE'] = '1'
os.environ['TQDM_MININTERVAL'] = '99999999'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")

# FastAPI 앱 초기화
# 환경에 따라 타이틀 변경 (dev/prod)
app_env = os.getenv("APP_ENV", "test").lower()
env_title_map = {
    "dev": "RAG Embedding Request Server (Dev)",
    "prod": "RAG Embedding Request Server (Prod)",
    "test": "RAG Embedding Request Server (Test)"
}
app_title = env_title_map.get(app_env, "RAG Embedding Request Server (Test)")

app = FastAPI(
    title=app_title,
    description="임베딩 요청 서버 - Kafka 발행 버전",
    version="0.1.0",
    openapi_url=None  # 명시적 라우트로 대체하기 위해 기본 URL 비활성화
)

# CORS 설정 추가 (스웨거 UI 테스트 등 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인에서의 요청 허용 (운영 환경에서는 구체적으로 제한 권장)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# 커스텀 OpenAPI 스펙 로드
def custom_openapi():
    """커스텀 openapi.yaml 파일을 로드하여 FastAPI OpenAPI 스펙으로 사용"""
    if app.openapi_schema:
        return app.openapi_schema
    
    # 프로젝트 루트의 openapi.yaml 파일 경로
    openapi_file = Path(__file__).parent.parent / "openapi.yaml"
    
    if openapi_file.exists():
        try:
            with open(openapi_file, "r", encoding="utf-8") as f:
                openapi_schema = yaml.safe_load(f)
            
            # 동적으로 타이틀 교체 (환경 변수 반영)
            if "info" in openapi_schema:
                openapi_schema["info"]["title"] = app.title
                
            # 환경에 따라 해당 서버를 최상단으로 이동
            if "servers" in openapi_schema:
                env_url_map = {
                    "dev": "http://localhost:8200",
                    "prod": "http://localhost:8100",
                }
                target_url = env_url_map.get(app_env)
                if target_url:
                    servers = openapi_schema["servers"]
                    servers.sort(key=lambda s: 0 if target_url in s.get("url", "") else 1)
                
            app.openapi_schema = openapi_schema
            logger.info(f"커스텀 OpenAPI 스펙 로드 완료: {openapi_file} (Title: {app.title})")
            return app.openapi_schema
        except Exception as e:
            logger.error(f"OpenAPI 스펙 로드 실패: {e}")
    
    # 파일이 없거나 로드 실패 시 기본 스펙 사용
    logger.warning(f"커스텀 OpenAPI 파일을 찾을 수 없습니다: {openapi_file}. 기본 스펙을 사용합니다.")
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = schema
    return app.openapi_schema

# FastAPI의 openapi() 메서드 오버라이드 (작동하지 않을 경우를 대비해 명시적 라우트 추가)
app.openapi = custom_openapi

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return custom_openapi()

from fastapi.openapi.docs import get_swagger_ui_html

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app.title + " - Swagger UI"
    )

# Kafka Producer 초기화
kafka_producer: Optional[KafkaProducerBase] = None

# 라운드로빈 파티션 카운터 (0 → 1 → 2 → 0 → ...)
# UUID 해시 기반 분배는 소량 메시지에서 특정 파티션에 쏠릴 수 있으므로
# 명시적 순환 방식으로 EW 간 균등 분배를 보장
_KAFKA_PARTITION_COUNT = 3
_partition_counter = itertools.cycle(range(_KAFKA_PARTITION_COUNT))

# MinIO 클라이언트 초기화
minio_client: Optional[MinIOClient] = None

# BGE-M3 임베딩 클라이언트 초기화 (질의 임베딩용)
embedder_client: Optional[BGEM3Client] = None
hybrid_embedder_client: Optional[BGEM3HybridClient] = None

# Qdrant 클라이언트 초기화 (재임베딩 시 기존 포인트 삭제용)
qdrant_client: Optional[QdrantVectorClient] = None


def get_minio_client() -> MinIOClient:
    """MinIO 클라이언트 싱글톤 인스턴스 반환"""
    global minio_client
    if minio_client is None:
        minio_client = MinIOClient()
        logger.debug(f"MinIO 클라이언트 초기화 완료: endpoint={settings.minio_endpoint}")
    return minio_client


def get_kafka_producer() -> KafkaProducerBase:
    """Kafka Producer 싱글톤 인스턴스 반환"""
    global kafka_producer
    if kafka_producer is None:
        bootstrap_servers = settings.kafka_bootstrap_servers.split(",")
        
        kafka_config = {
            'bootstrap_servers': bootstrap_servers,
            'value_serializer': lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
            'key_serializer': lambda k: k.encode('utf-8') if k else None,
            'acks': 'all',
            'retries': 3,
            'max_in_flight_requests_per_connection': 1,
        }
        
        # SASL 인증 설정 (운영 환경)
        if settings.kafka_security_protocol != "PLAINTEXT":
            kafka_config['security_protocol'] = settings.kafka_security_protocol
            kafka_config['sasl_mechanism'] = settings.kafka_sasl_mechanism
            kafka_config['sasl_plain_username'] = settings.kafka_sasl_username
            kafka_config['sasl_plain_password'] = settings.kafka_sasl_password
        
        kafka_producer = KafkaProducerBase(**kafka_config)
        logger.debug(f"Kafka Producer 초기화 완료: bootstrap_servers={bootstrap_servers}")
    return kafka_producer


def get_qdrant_client() -> QdrantVectorClient:
    """Qdrant 클라이언트 싱글톤 인스턴스 반환"""
    global qdrant_client
    if qdrant_client is None:
        qdrant_client = QdrantVectorClient()
        logger.debug("Qdrant 클라이언트 초기화 완료")
    return qdrant_client


def get_embedder_client() -> BGEM3Client:
    """BGE-M3 임베딩 클라이언트 싱글톤 인스턴스 반환"""
    global embedder_client
    if embedder_client is None:
        embedder_client = BGEM3Client()
        logger.debug("BGEM3Client 초기화 완료")
    return embedder_client


def get_hybrid_embedder_client() -> BGEM3HybridClient:
    """BGE-M3 하이브리드 임베딩 클라이언트 싱글톤 인스턴스 반환"""
    global hybrid_embedder_client
    if hybrid_embedder_client is None:
        hybrid_embedder_client = BGEM3HybridClient()
        logger.debug("BGEM3HybridClient 초기화 완료")
    return hybrid_embedder_client


class EmbeddingRequest(BaseModel):
    """임베딩 요청 모델"""
    doc_content_id: Union[UUID, str] = Field(..., description="이미 생성된 문서 컨텐츠 ID")
    sha256: Optional[str] = Field(
        default=None,
        description="파일 SHA-256 해시값 (중복 검사용)"
    )
    local_path: Optional[str] = Field(
        default=None,
        description="로컬 파일 경로"
    )
    minio_bucket: Optional[str] = Field(
        default=None,
        description="MinIO 버킷 이름"
    )
    minio_object_key: Optional[str] = Field(
        default=None,
        description="MinIO 객체 키"
    )
    embedding_profile: Literal["bge_m3_v1", "bge_m3_hybrid_v2"] = Field(
        default="bge_m3_v1",
        description="임베딩 프로필 (bge_m3_v1: 기존 dense 전용, bge_m3_hybrid_v2: dense+sparse 하이브리드)"
    )
    enable_ocr: bool = Field(
        default=False,
        description="OCR 활성화 (이미지/스캔 문서 처리). 모든 지원 형식(PDF/DOC/DOCX/PPT/PPTX/XLSX/XLSM/HWP/HWPX)에서 동작. OCR 텍스트는 본문 흐름 안에 inline으로 삽입되어 같은 청크에서 검색됨 — HWPX는 paragraph 위치 정확, HWP는 본문 길이 비례 균등 분산, PPTX는 슬라이드 내 결합, XLSX는 시트 마지막 row에 추가. XLS/CSV/TXT 등 이미지 없는 형식에서는 무시됨."
    )
    extraction_version: Optional[str] = Field(default=None, description="텍스트 추출 파이프라인 버전 (예: v1.0.1)")
    requested_by: str = Field(..., description="요청자 식별자")
    auth_dept_id: Union[UUID, str] = Field(..., description="요청자 부서 ID")

    @model_validator(mode="after")
    def validate_source(self):
        if not self.local_path and not (self.minio_bucket and self.minio_object_key):
            raise ValueError("local_path 또는 minio_bucket + minio_object_key 중 하나는 필수입니다.")
        return self


class EmbeddingRequestResponse(BaseModel):
    """임베딩 요청 응답 모델"""
    job_id: str
    doc_content_id: Union[UUID, str] = Field(
        ..., description="이미 생성된 문서 컨텐츠 ID"
    )
    local_path: Optional[str] = None
    minio_bucket: Optional[str] = None
    minio_object_key: Optional[str] = None
    embedding_profile: str
    requested_by: str
    auth_dept_id: Union[UUID, str]
    requested_at: str


# 재임베딩 시 서버에서 하드코딩으로 사용하는 값들
# 추출 로직/모델 업데이트 시 이 상수만 수정하면 됨 (백엔드 변경 불필요)
RE_EMBEDDING_REASON = "텍스트 추출 로직 개선"
# 형식: v<semver>-<ocr_provider>-r<retry_threshold*100>-u<retry_upscale*10>
# 예: v1.2.0-nemotron-r080-u20 → Nemotron OCR v2, 재추론 임계값 0.80, upscale 2.0
# 텍스트 PDF 등 OCR 미사용 케이스도 동일 버전 문자열로 인덱싱 (실제 OCR 호출 여부는
# chunks.metadata.enable_ocr / doc_document_content.enable_ocr 로 별도 추적).
EXTRACTION_VERSION = "v1.2.0-nemotron-r080-u20"


class ReEmbeddingRequest(BaseModel):
    """재임베딩 요청 모델"""
    doc_content_id: Union[UUID, str] = Field(..., description="재임베딩할 문서 컨텐츠 ID")
    embedding_profile: Literal["bge_m3_v1", "bge_m3_hybrid_v2"] = Field(
        default="bge_m3_v1",
        description="임베딩 프로필 (bge_m3_v1: 기존 dense 전용, bge_m3_hybrid_v2: dense+sparse 하이브리드)"
    )
    embedding_mode: Literal["re_chunk", "re_vectorize"] = Field(
        default="re_chunk",
        description="re_chunk=텍스트 추출+청킹부터 다시. re_vectorize=기존 청크 재활용해 벡터만 새로 (다른 버전 임베딩 보존)."
    )
    enable_ocr: bool = Field(
        default=False,
        description="OCR 활성화 (이미지/스캔 문서 처리). 모든 지원 형식(PDF/DOC/DOCX/PPT/PPTX/XLSX/XLSM/HWP/HWPX)에서 동작 — OCR 텍스트는 본문 흐름 안에 inline 삽입. re_chunk일 때만 의미 있음 (re_vectorize는 기존 청크 재사용)."
    )
    requested_by: str = Field(..., description="요청자 식별자")
    force: bool = Field(default=False, description="진행 중인 작업(QUEUED/PARSING/EMBEDDING)도 무시하고 강제 재임베딩")


class QueryRequest(BaseModel):
    """질의 임베딩 요청 모델"""
    query: str = Field(..., description="임베딩할 질의 문장")


@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 시 Kafka Producer, MinIO 클라이언트 및 임베딩 클라이언트 초기화"""
    logger.info("ER 서버 시작 중...")
    get_kafka_producer()
    get_minio_client()
    get_embedder_client()
    get_qdrant_client()
    logger.info("ER 서버 초기화 완료")
    logger.debug(f"Kafka 설정: bootstrap_servers={settings.kafka_bootstrap_servers}, "
                f"request_topic={settings.kafka_request_topic}")
    logger.debug(f"MinIO 설정: endpoint={settings.minio_endpoint}, "
                f"bucket={settings.minio_bucket}")


@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 시 Kafka Producer 정리"""
    global kafka_producer
    if kafka_producer:
        kafka_producer.flush()
        kafka_producer.close()
        logger.info("Kafka Producer 종료 완료")


@app.post("/embedding-requests", response_model=EmbeddingRequestResponse)
async def create_embedding_request(request: EmbeddingRequest):
    """
    임베딩 요청 생성 및 Kafka 메시지 발행
    
    요청 바디:
    - local_path: 로컬 파일 경로
    - embedding_profile: 임베딩 프로필
    - requested_by: 요청자 식별자
    
    응답:
    - job_id: 생성된 Job ID (UUID)
    - 요청 정보 전체
    """
    # (1) 요청 바디 검증 (Pydantic이 자동으로 처리)
    logger.info(
        f"임베딩 요청 수신: local_path={request.local_path}, "
        f"sha256={request.sha256[:16] + '...' if request.sha256 else 'N/A'}, "
        f"embedding_profile={request.embedding_profile}, "
        f"requested_by={request.requested_by}, "
        f"auth_dept_id={request.auth_dept_id}"
    )
    
    doc_content_uuid = UUID(str(request.doc_content_id))
    doc_content_id = str(doc_content_uuid)
    job_id: Optional[str] = None
    minio_bucket = None
    minio_object_key = None
    original_filename = None
    mime_type = None
    file_size = None
    response_local_path: Optional[str] = None
    
    if request.local_path:
        safe_path = Path(request.local_path.replace("\\\\", "\\")).expanduser()
        
        if not safe_path.exists():
            logger.warning(
                f"임베딩 요청 거부(400 Bad Request): 로컬 파일이 존재하지 않습니다. "
                f"local_path={safe_path}, requested_by={request.requested_by}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"파일을 찾을 수 없습니다: {safe_path}"
            )
        
        if not safe_path.is_file():
            logger.warning(
                f"임베딩 요청 거부(400 Bad Request): 로컬 경로가 파일이 아닙니다. "
                f"local_path={safe_path}, requested_by={request.requested_by}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"파일이 아닙니다: {safe_path}"
            )
        
        try:
            with open(safe_path, "rb") as f:
                file_data = f.read()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"파일 읽기 실패: {str(e)}"
            )
        
        original_filename = safe_path.name
        mime_type, _ = mimetypes.guess_type(str(safe_path))
        if not mime_type:
            ext = safe_path.suffix.lower()
            mime_type_map = {
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".doc": "application/msword",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xls": "application/vnd.ms-excel",
                ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ".ppt": "application/vnd.ms-powerpoint",
                ".txt": "text/plain",
                ".csv": "text/csv",
            }
            mime_type = mime_type_map.get(ext, "application/octet-stream")
        
        logger.info(f"파일 정보: filename={original_filename}, mime_type={mime_type}, size={len(file_data)} bytes")
        
        minio = get_minio_client()
        minio_bucket = settings.minio_bucket
        minio_object_key = f"raw/{doc_content_id}/{original_filename}"
        
        try:
            minio.upload_object(
                bucket=minio_bucket,
                object_key=minio_object_key,
                data=file_data,
                content_type=mime_type
            )
            file_size = len(file_data)
            logger.info(f"MinIO 업로드 완료: {minio_bucket}/{minio_object_key}")
        except Exception as e:
            logger.error(f"MinIO 업로드 실패: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"MinIO 업로드 실패: {str(e)}"
            )
        
        response_local_path = str(safe_path)
    
    else:
        minio_bucket = request.minio_bucket
        minio_object_key = request.minio_object_key
        if not minio_bucket or not minio_object_key:
            raise HTTPException(
                status_code=400,
                detail="minio_bucket과 minio_object_key가 필요합니다."
            )
        
        original_filename = minio_object_key.split("/")[-1] or minio_object_key
        mime_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
        
        minio = get_minio_client()
        metadata = minio.get_object_metadata(minio_bucket, minio_object_key)
        if not metadata:
            logger.warning(
                f"임베딩 요청 거부(404 Not Found): MinIO 객체가 존재하지 않습니다. "
                f"bucket={minio_bucket}, key={minio_object_key}, requested_by={request.requested_by}"
            )
            raise HTTPException(
                status_code=404,
                detail=f"MinIO 객체를 찾을 수 없습니다: {minio_bucket}/{minio_object_key}"
            )
        file_size = metadata.get("size")
        logger.info(
            f"MinIO 객체 확인 완료: bucket={minio_bucket}, key={minio_object_key}, "
            f"size={metadata.get('size')}"
        )
    
    if not (minio_bucket and minio_object_key):
        raise HTTPException(
            status_code=400,
            detail="minio_bucket과 minio_object_key가 필요합니다."
        )

    job_record = None
    try:
        with get_db_session() as session:
            # doc_content_id로 문서 조회 (SHA-256 중복 검사를 위해 먼저 조회)
            doc_version = DocumentContentRepository.get_by_id(session, doc_content_uuid)
            if not doc_version:
                logger.warning(
                    f"임베딩 요청 거부(404 Not Found): 문서 컨텐츠가 DB에 존재하지 않습니다. "
                    f"bucket={minio_bucket}, key={minio_object_key}, doc_content_id={doc_content_id}, "
                    f"requested_by={request.requested_by}"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"문서 컨텐츠를 찾을 수 없습니다: {doc_content_id}"
                )
            
            # SHA-256 기반 중복 검사 (DB에서 가져온 sha256 값 사용)
            current_sha256 = doc_version.sha256
            if current_sha256:
                # 같은 SHA-256을 가진 다른 문서 찾기 (자기 자신 제외)
                existing_doc = (
                    session.query(DocDocumentContent)
                    .filter(
                        DocDocumentContent.sha256 == current_sha256,
                        DocDocumentContent.id != doc_content_uuid
                    )
                    .first()
                )
                
                if existing_doc:
                    # 임베딩 진행 중이거나 완료된 상태만 중복으로 처리
                    # UPLOADED, FAILED 상태는 허용 (아직 임베딩 안 됨 or 재시도 가능)
                    blocking_statuses = [
                        DocumentStatus.QUEUED.value,
                        DocumentStatus.PARSING.value,
                        DocumentStatus.EMBEDDING.value,
                        DocumentStatus.COMPLETED.value,
                    ]
                    
                    if existing_doc.status in blocking_statuses:
                        status_msg = {
                            DocumentStatus.COMPLETED.value: "이미 임베딩 완료",
                            DocumentStatus.QUEUED.value: "임베딩 대기 중",
                            DocumentStatus.PARSING.value: "파싱 중",
                            DocumentStatus.EMBEDDING.value: "임베딩 중",
                        }.get(existing_doc.status, f"처리 중 (상태: {existing_doc.status})")
                        
                        logger.warning(
                            f"중복 파일 검출(409 Conflict): 동일한 SHA-256 해시를 가진 파일이 {status_msg}입니다. "
                            f"sha256={current_sha256[:16]}..., existing_doc_content_id={existing_doc.id}, "
                            f"current_doc_content_id={doc_content_id}, "
                            f"original_filename={existing_doc.original_filename}, "
                            f"status={existing_doc.status}, requested_by={request.requested_by}"
                        )
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "error": "duplicate_file",
                                "message": f"동일한 파일이 {status_msg}입니다 (SHA-256 해시 일치)",
                                "existing_doc_content_id": str(existing_doc.id),
                                "current_doc_content_id": doc_content_id,
                                "original_filename": existing_doc.original_filename,
                                "status": existing_doc.status,
                                "completed_at": existing_doc.finished_at.isoformat() if existing_doc.finished_at else None,
                                "sha256": current_sha256
                            }
                        )
                    else:
                        # UPLOADED, FAILED 등 임베딩 진행 가능한 상태
                        logger.info(
                            f"동일 SHA-256 파일 존재하지만 임베딩 허용: sha256={current_sha256[:16]}..., "
                            f"existing_doc_content_id={existing_doc.id}, existing_status={existing_doc.status}, "
                            f"current_doc_content_id={doc_content_id}"
                        )

            if doc_version.status not in (DocumentStatus.UPLOADED.value, DocumentStatus.PENDING_APPROVAL.value):
                logger.warning(
                    "중복 임베딩 요청 거부(409 Conflict): 문서 상태가 UPLOADED가 아닙니다. "
                    f"bucket={minio_bucket}, key={minio_object_key}, "
                    f"doc_id={doc_version.document_id}, doc_content_id={doc_content_id}, "
                    f"current_status={doc_version.status}, requested_by={request.requested_by}"
                )
                raise HTTPException(
                    status_code=409,
                    detail=f"문서 컨텐츠 상태가 업로드 완료가 아닙니다 (현재: {doc_version.status})"
                )

            DocumentContentRepository.update_status(
                session,
                doc_content_uuid,
                DocumentStatus.QUEUED
            )

            raw_payload = {
                "doc_content_id": doc_content_id,
                "document_id": doc_version.document_id,
                "minio_bucket": minio_bucket,
                "minio_object_key": minio_object_key,
                "original_filename": original_filename,
                "mime_type": mime_type,
                "file_size": file_size,
                "embedding_profile": request.embedding_profile,
                "enable_ocr": request.enable_ocr,
                "extraction_version": EXTRACTION_VERSION,
                "requested_by": request.requested_by,
            }
            payload_json = to_jsonable(raw_payload)

            job_record = EmbeddingJobRepository.create(
                session,
                doc_content_id=doc_content_uuid,
                kafka_topic=settings.kafka_request_topic,
                kafka_key=doc_content_id,
                payload_json=payload_json,
                status=JobStatus.QUEUED,
            )

            StatusEventRepository.record(
                session,
                doc_content_id=doc_content_uuid,
                job_id=job_record.id,
                status=StatusEventType.QUEUED.value,
                source=EventSource.ER.value,
                message="임베딩 Job 생성",
                metadata={
                    "bucket": minio_bucket,
                    "object_key": minio_object_key,
                    "requested_by": request.requested_by,
                    "auth_dept_id": str(request.auth_dept_id),
                },
            )

            job_id = str(job_record.id)
    except HTTPException:
        raise
    except Exception as db_error:
        logger.exception("임베딩 Job 생성 중 오류: %s", db_error)
        raise HTTPException(status_code=500, detail="임베딩 Job 생성 실패")
    
    # (6) Kafka 메시지 발행 (JobPayload 형식에 맞춤)
    requested_at = datetime.utcnow().isoformat() + "Z"
    
    kafka_payload = {
        "job_id": job_id,
        "doc_content_id": doc_content_id,
        "minio_bucket": minio_bucket,
        "minio_object_key": minio_object_key,
        "original_filename": original_filename,
        "mime_type": mime_type,
        "auth_dept_id": str(request.auth_dept_id),
        "extraction_version": EXTRACTION_VERSION,
        "embedding_profile": request.embedding_profile,
        "enable_ocr": request.enable_ocr,
    }

    try:
        producer = get_kafka_producer()
        topic = settings.kafka_request_topic

        # 라운드로빈으로 파티션 직접 지정 (0 → 1 → 2 → 0 → ...)
        # UUID 해시 기반 분배는 소량 메시지에서 특정 파티션에 쏠릴 수 있으므로
        # 순환 카운터로 EW 간 균등 분배를 보장
        partition = next(_partition_counter)
        
        logger.info(
            f"Kafka 메시지 발행 시도: topic={topic}, job_id={job_id}, "
            f"doc_content_id={doc_content_id}, partition={partition}, minio_object_key={minio_object_key}"
        )
        
        # Kafka 메시지 전송 (파티션 직접 지정으로 라운드로빈 분배)
        future = producer.send(
            topic,
            value=kafka_payload,
            key=doc_content_id,
            partition=partition
        )
        
        # 전송 완료 대기 (타임아웃 10초)
        record_metadata = future.get(timeout=10)
        
        logger.info(
            f"Kafka 메시지 발행 완료: topic={record_metadata.topic}, "
            f"partition={record_metadata.partition}, offset={record_metadata.offset}, "
            f"job_id={job_id}"
        )
        
        # Kafka partition과 offset 정보를 DB에 저장
        if job_record:
            try:
                with get_db_session() as session:
                    EmbeddingJobRepository.update_kafka_metadata(
                        session,
                        job_record.id,
                        partition=record_metadata.partition,
                        offset=record_metadata.offset,
                    )
                    logger.debug(
                        f"Kafka 메타데이터 저장 완료: job_id={job_id}, "
                        f"partition={record_metadata.partition}, offset={record_metadata.offset}"
                    )
            except Exception as e:
                logger.warning(
                    f"Kafka 메타데이터 저장 실패 (처리는 계속됨): job_id={job_id}, 에러: {e}"
                )
        
    except KafkaError as e:
        logger.error(
            f"Kafka 메시지 발행 실패: job_id={job_id}, doc_content_id={doc_content_id}, 에러: {e}"
        )
        if job_record:
            try:
                with get_db_session() as session:
                    EmbeddingJobRepository.update_status(
                        session,
                        job_record.id,
                        JobStatus.FAILED,
                        error_message=str(e)
                    )
                    DocumentContentRepository.update_status(
                        session,
                        doc_content_uuid,
                        DocumentStatus.UPLOADED,
                        status_reason="Kafka publish failed"
                    )
                    StatusEventRepository.record(
                        session,
                        doc_content_id=doc_content_uuid,
                        job_id=job_record.id,
                        status=StatusEventType.FAILED.value,
                        source=EventSource.ER.value,
                        message="Kafka 발행 실패",
                        metadata={"error": str(e)},
                    )
            except Exception as update_error:
                logger.error("Kafka 실패 처리 중 DB 업데이트 실패: %s", update_error)
        raise HTTPException(
            status_code=500,
            detail=f"Kafka 메시지 발행 실패: {str(e)}"
        )
    except Exception as e:
        logger.exception(
            f"예상치 못한 에러 발생: job_id={job_id}, local_path={request.local_path}, "
            f"에러: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"서버 내부 오류: {str(e)}"
        )
    
    # (4) 클라이언트에 응답 반환
    response = EmbeddingRequestResponse(
        job_id=job_id,
        doc_content_id=doc_content_id,
        local_path=response_local_path,
        minio_bucket=minio_bucket,
        minio_object_key=minio_object_key,
        embedding_profile=request.embedding_profile,
        requested_by=request.requested_by,
        auth_dept_id=request.auth_dept_id,
        requested_at=requested_at
    )
    
    logger.info(f"임베딩 요청 처리 완료: job_id={job_id}")
    
    return response


@app.post("/re-embedding-requests", response_model=EmbeddingRequestResponse)
async def create_re_embedding_request(request: ReEmbeddingRequest):
    """
    재임베딩 요청 생성

    이미 임베딩 완료(COMPLETED) 또는 실패(FAILED) 상태의 문서를 재임베딩합니다.
    기존 청크, 임베딩 인덱스, Qdrant 포인트, 처리 통계를 정리한 후
    새로운 임베딩 Job을 생성합니다.

    사용 사례:
    - 텍스트 추출 기법(OCR 포함) 업데이트
    - 임베딩 모델 변경
    - 청킹 전략 변경
    - 기존 임베딩 품질 문제 발견
    """
    doc_content_uuid = UUID(str(request.doc_content_id))
    doc_content_id = str(doc_content_uuid)

    logger.info(
        "재임베딩 요청 수신: doc_content_id=%s, reason=%s, force=%s, requested_by=%s",
        doc_content_id, RE_EMBEDDING_REASON, request.force, request.requested_by,
    )

    job_record = None
    minio_bucket = None
    minio_object_key = None
    original_filename = None
    mime_type = None
    job_id: Optional[str] = None

    try:
        with get_db_session() as session:
            # (1) 문서 조회
            doc_version = DocumentContentRepository.get_by_id(session, doc_content_uuid)
            if not doc_version:
                raise HTTPException(
                    status_code=404,
                    detail=f"문서 컨텐츠를 찾을 수 없습니다: {doc_content_id}"
                )

            # (2) 상태 검증
            current_status = doc_version.status
            allowed_statuses = [DocumentStatus.COMPLETED.value, DocumentStatus.FAILED.value]
            in_progress_statuses = [
                DocumentStatus.QUEUED.value,
                DocumentStatus.PARSING.value,
                DocumentStatus.EMBEDDING.value,
            ]

            if current_status == DocumentStatus.UPLOADED.value:
                raise HTTPException(
                    status_code=409,
                    detail="아직 임베딩되지 않은 문서입니다. 일반 임베딩 요청(/embedding-requests)을 사용해주세요."
                )

            if current_status in in_progress_statuses:
                if not request.force:
                    raise HTTPException(
                        status_code=409,
                        detail=f"문서가 현재 처리 중입니다 (상태: {current_status}). "
                               f"강제 재임베딩하려면 force=true로 요청해주세요."
                    )
                logger.warning(
                    "강제 재임베딩: 진행 중인 작업 무시. doc_content_id=%s, current_status=%s",
                    doc_content_id, current_status,
                )

            if current_status not in allowed_statuses and current_status not in in_progress_statuses:
                raise HTTPException(
                    status_code=409,
                    detail=f"재임베딩할 수 없는 상태입니다 (현재: {current_status})"
                )

            # (2-1) re_vectorize 모드는 기존 청크가 있어야만 가능
            if request.embedding_mode == "re_vectorize":
                existing_chunks = ChunkRepository.get_by_doc_content(session, doc_content_uuid)
                if not existing_chunks:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "re_vectorize 모드는 기존 청크가 있는 문서에서만 사용 가능합니다. "
                            "청크가 없으므로 embedding_mode=re_chunk 로 요청하세요."
                        ),
                    )
                logger.info(
                    "re_vectorize 검증 통과: doc_content_id=%s, existing_chunks=%d",
                    doc_content_id, len(existing_chunks),
                )

            # (3) doc_document_content.auth_dept_id 에서 원본 부서코드 조회
            # 재임베딩 시 요청 파라미터의 auth_dept_id는 무시하고, 문서에 저장된 부서코드 사용
            if doc_version.auth_dept_id:
                original_auth_dept_id = str(doc_version.auth_dept_id)
                logger.info(
                    "원본 부서코드 조회 성공: doc_content_id=%s, auth_dept_id=%s",
                    doc_content_id, original_auth_dept_id,
                )
            else:
                logger.error(
                    "doc_document_content.auth_dept_id가 비어 있습니다: doc_content_id=%s",
                    doc_content_id,
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"문서의 부서코드가 설정되지 않았습니다: doc_content_id={doc_content_id}"
                )

            # (4) MinIO에서 원본 파일 정보 확인 (storage_object_files 테이블에서 실제 경로 조회)
            storage_obj = StorageObjectRepository.get_raw_by_doc_content_id(session, doc_content_uuid)
            if not storage_obj:
                raise HTTPException(
                    status_code=404,
                    detail=f"원본 파일의 저장 정보를 찾을 수 없습니다: doc_content_id={doc_content_id}"
                )

            minio = get_minio_client()
            minio_bucket = storage_obj.bucket
            minio_object_key = storage_obj.object_key
            original_filename = doc_version.original_filename
            mime_type = doc_version.mime_type

            metadata = minio.get_object_metadata(minio_bucket, minio_object_key)
            if not metadata:
                raise HTTPException(
                    status_code=404,
                    detail=f"원본 파일을 MinIO에서 찾을 수 없습니다: {minio_bucket}/{minio_object_key}"
                )

            # NOTE: 기존 임베딩 데이터(청크/인덱스/Qdrant/통계)는 EW 워커가 새 임베딩 처리 직전에
            # 삭제합니다. 큐 대기 중에 검색 데이터가 비어 있는 윈도우를 없애기 위함입니다.

            # (5) 문서 상태를 QUEUED로 변경
            DocumentContentRepository.update_status(
                session,
                doc_content_uuid,
                DocumentStatus.QUEUED
            )

            # (6) 새 Job 생성
            raw_payload = {
                "doc_content_id": doc_content_id,
                "document_id": doc_version.document_id,
                "minio_bucket": minio_bucket,
                "minio_object_key": minio_object_key,
                "original_filename": original_filename,
                "mime_type": mime_type,
                "file_size": doc_version.file_size,
                "embedding_profile": request.embedding_profile,
                "embedding_mode": request.embedding_mode,
                "extraction_version": EXTRACTION_VERSION,
                "enable_ocr": request.enable_ocr,
                "requested_by": request.requested_by,
                "re_embedding": True,
                "re_embedding_reason": RE_EMBEDDING_REASON,
            }
            payload_json = to_jsonable(raw_payload)

            job_record = EmbeddingJobRepository.create(
                session,
                doc_content_id=doc_content_uuid,
                kafka_topic=settings.kafka_request_topic,
                kafka_key=doc_content_id,
                payload_json=payload_json,
                status=JobStatus.QUEUED,
            )

            StatusEventRepository.record(
                session,
                doc_content_id=doc_content_uuid,
                job_id=job_record.id,
                status=StatusEventType.RE_EMBEDDING_REQUESTED.value,
                source=EventSource.ER.value,
                message=f"재임베딩 요청: {RE_EMBEDDING_REASON}",
                metadata={
                    "reason": RE_EMBEDDING_REASON,
                    "force": request.force,
                    "requested_by": request.requested_by,
                    "auth_dept_id": original_auth_dept_id,
                    "previous_status": current_status,
                },
            )

            job_id = str(job_record.id)

    except HTTPException:
        raise
    except Exception as db_error:
        logger.exception("재임베딩 Job 생성 중 오류: %s", db_error)
        raise HTTPException(status_code=500, detail="재임베딩 Job 생성 실패")

    # (7) Kafka 메시지 발행
    requested_at = datetime.utcnow().isoformat() + "Z"

    kafka_payload = {
        "job_id": job_id,
        "doc_content_id": doc_content_id,
        "minio_bucket": minio_bucket,
        "minio_object_key": minio_object_key,
        "original_filename": original_filename,
        "mime_type": mime_type,
        "auth_dept_id": original_auth_dept_id,
        "extraction_version": EXTRACTION_VERSION,
        "embedding_profile": request.embedding_profile,
        "embedding_mode": request.embedding_mode,
        "enable_ocr": request.enable_ocr,
        "re_embedding": True,
        "re_embedding_reason": RE_EMBEDDING_REASON,
    }

    try:
        producer = get_kafka_producer()
        topic = settings.kafka_request_topic
        partition = next(_partition_counter)

        logger.info(
            "Kafka 재임베딩 메시지 발행 시도: topic=%s, job_id=%s, "
            "doc_content_id=%s, partition=%d",
            topic, job_id, doc_content_id, partition,
        )

        future = producer.send(
            topic,
            value=kafka_payload,
            key=doc_content_id,
            partition=partition,
        )
        record_metadata = future.get(timeout=10)

        logger.info(
            "Kafka 재임베딩 메시지 발행 완료: topic=%s, partition=%d, offset=%d, job_id=%s",
            record_metadata.topic, record_metadata.partition,
            record_metadata.offset, job_id,
        )

        if job_record:
            try:
                with get_db_session() as session:
                    EmbeddingJobRepository.update_kafka_metadata(
                        session,
                        job_record.id,
                        partition=record_metadata.partition,
                        offset=record_metadata.offset,
                    )
            except Exception as e:
                logger.warning(
                    "Kafka 메타데이터 저장 실패 (처리는 계속됨): job_id=%s, 에러: %s",
                    job_id, e,
                )

    except KafkaError as e:
        logger.error(
            "Kafka 재임베딩 메시지 발행 실패: job_id=%s, doc_content_id=%s, 에러: %s",
            job_id, doc_content_id, e,
        )
        if job_record:
            try:
                with get_db_session() as session:
                    EmbeddingJobRepository.update_status(
                        session, job_record.id, JobStatus.FAILED,
                        error_message=str(e),
                    )
                    DocumentContentRepository.update_status(
                        session, doc_content_uuid, DocumentStatus.FAILED,
                        status_reason="Kafka publish failed (re-embedding)",
                        status_message="AI 지식 추가 도중 알 수 없는 원인으로 실패하였습니다. 재시도 해주세요.",
                    )
                    StatusEventRepository.record(
                        session,
                        doc_content_id=doc_content_uuid,
                        job_id=job_record.id,
                        status=StatusEventType.FAILED.value,
                        source=EventSource.ER.value,
                        message="재임베딩 Kafka 발행 실패",
                        metadata={"error": str(e)},
                    )
            except Exception as update_error:
                logger.error("Kafka 실패 처리 중 DB 업데이트 실패: %s", update_error)
        raise HTTPException(
            status_code=500,
            detail=f"Kafka 메시지 발행 실패: {str(e)}"
        )

    response = EmbeddingRequestResponse(
        job_id=job_id,
        doc_content_id=doc_content_id,
        local_path=None,
        minio_bucket=minio_bucket,
        minio_object_key=minio_object_key,
        embedding_profile=request.embedding_profile,
        requested_by=request.requested_by,
        auth_dept_id=original_auth_dept_id,
        requested_at=requested_at,
    )

    logger.info("재임베딩 요청 처리 완료: job_id=%s, doc_content_id=%s", job_id, doc_content_id)
    return response


@app.post("/query")
async def query_embeddings(body: QueryRequest) -> Dict[str, Any]:
    """
    질의 문장을 임베딩 벡터로 변환
    
    요청 바디:
    - query: 임베딩할 질의 문장
    
    응답:
    - query: 입력한 질의 문장
    - model: 사용한 임베딩 모델 이름
    - model_path: 모델 경로
    - dim: 벡터 차원 수
    - vector: 임베딩 벡터 (리스트)
    """
    query = body.query.strip()
    
    # 요청 수신 로그
    logger.info(f"질의 임베딩 요청 수신: query='{query[:100]}{'...' if len(query) > 100 else ''}'")
    
    if not query:
        logger.warning("질의 임베딩 요청 거부: 빈 쿼리")
        raise HTTPException(status_code=400, detail="query가 비어 있습니다.")
    
    try:
        # 임베딩 처리 시작 로그
        logger.info(f"질의 임베딩 처리 시작: query_length={len(query)}")
        
        embedder = get_embedder_client()
        vector = embedder.embed_text(query)
        
        # 임베딩 처리 완료 로그
        logger.info(
            f"질의 임베딩 처리 완료: query_length={len(query)}, "
            f"vector_dim={len(vector)}, model=bge-m3"
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"임베딩 실패: query={query}, error={exc}")
        raise HTTPException(status_code=500, detail=f"임베딩 실패: {exc}") from exc
    
    return {
        "query": query,
        "model": "bge-m3",
        "model_path": getattr(settings, "bge_m3_model_path", "BAAI/bge-m3"),
        "dim": len(vector),
        "vector": vector,
    }


@app.post("/query-hybrid")
async def query_hybrid_embeddings(body: QueryRequest) -> Dict[str, Any]:
    """
    질의 문장을 하이브리드 임베딩(dense + sparse)으로 변환

    요청 바디:
    - query: 임베딩할 질의 문장

    응답:
    - query: 입력한 질의 문장
    - model: 사용한 임베딩 모델 이름
    - dim: dense 벡터 차원 수
    - dense: dense 임베딩 벡터
    - sparse: sparse 임베딩 벡터 (indices, values)
    """
    query = body.query.strip()

    logger.info(f"질의 하이브리드 임베딩 요청 수신: query='{query[:100]}{'...' if len(query) > 100 else ''}'")

    if not query:
        logger.warning("질의 하이브리드 임베딩 요청 거부: 빈 쿼리")
        raise HTTPException(status_code=400, detail="query가 비어 있습니다.")

    try:
        logger.info(f"질의 하이브리드 임베딩 처리 시작: query_length={len(query)}")

        embedder = get_hybrid_embedder_client()
        result = embedder.embed_text(query)

        logger.info(
            f"질의 하이브리드 임베딩 처리 완료: query_length={len(query)}, "
            f"dense_dim={len(result['dense'])}, "
            f"sparse_terms={len(result['sparse']['indices'])}, model=bge-m3-hybrid"
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"하이브리드 임베딩 실패: query={query}, error={exc}")
        raise HTTPException(status_code=500, detail=f"하이브리드 임베딩 실패: {exc}") from exc

    return {
        "query": query,
        "model": "bge-m3-hybrid",
        "dim": len(result["dense"]),
        "dense": result["dense"],
        "sparse": result["sparse"],
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "ok",
        "service": "ER (Embedding Request Server)",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)

