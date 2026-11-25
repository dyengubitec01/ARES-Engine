"""열거형 정의"""
from enum import Enum


class DocumentStatus(str, Enum):
    """문서 상태"""
    UPLOADED = "uploaded"
    PENDING_APPROVAL = "pending_approval"
    QUEUED = "queued"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"
    DUPLICATED = "duplicated"


class JobStatus(str, Enum):
    """임베딩 Job 상태"""
    QUEUED = "queued"
    STARTED = "started"
    EMBEDDING = "embedding"
    UPSERTING = "upserting"
    DONE = "done"
    FAILED = "failed"


class ObjectKind(str, Enum):
    """MinIO 객체 종류"""
    RAW = "raw"
    ORIGIN = "origin"
    CHUNKS = "chunks"
    CHUNKS_METADATA = "chunks_metadata"
    METADATA = "metadata"
    EMBEDDING = "embeddings"
    STATS = "stats"


class DistanceMetric(str, Enum):
    """Qdrant 거리 메트릭"""
    COSINE = "cosine"
    DOT = "dot"
    EUCLIDEAN = "euclidean"


class UserRole(str, Enum):
    """사용자 역할"""
    ADMIN = "admin"
    MEMBER = "member"
    SYSTEM = "system"


class EventSource(str, Enum):
    """상태 이벤트 소스"""
    ER = "er"
    EW = "ew"
    BE = "be"
    SYSTEM = "system"


class StatusEventType(str, Enum):
    """상태 이벤트 타입"""
    # ER 서버
    QUEUED = "queued"
    FAILED = "failed"
    
    # EW 워커 - 정상 플로우
    STARTED = "started"
    CHUNKED = "chunked"
    EMBEDDING = "embedding"
    QDRANT_UPSERTED = "qdrant_upserted"
    DONE = "done"
    
    # EW 워커 - 예외 처리
    SKIPPED = "skipped"
    RETRY = "retry"
    FAILED_PERMANENT = "failed_permanent"
    
    # 중복 감지
    DUPLICATE_WARNING = "duplicate_warning"

    # 재임베딩
    RE_EMBEDDING_REQUESTED = "re_embedding_requested"








