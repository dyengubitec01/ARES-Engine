"""
RAG 임베딩 파이프라인 설정 관리

환경변수 기반 설정:
- 로컬 개발(로컬 Python 실행): 기본값 localhost 사용
- Docker 컨테이너(ER/EW): docker-compose.yml의 환경변수로 override
  예: KAFKA_BOOTSTRAP_SERVERS=kafka:29092, MINIO_ENDPOINT=minio:9000 등
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # 애플리케이션
    app_name: str = "RAG Embedding Pipeline"
    debug: bool = False
    
    # ============================================
    # PostgreSQL 설정
    # ============================================
    # 로컬 개발: localhost:5432 (기본값)
    # Docker 컨테이너: postgres:5432 (환경변수로 override)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres_user"
    postgres_password: str = "dusrnth25!!"
    postgres_db: str = "ragdb"
    postgres_schema: str = "rag"  # 기본 스키마: rag
    postgres_url: Optional[str] = None
    
    # ============================================
    # Kafka 설정
    # ============================================
    # 로컬 개발: localhost:9092 (기본값)
    # Docker 컨테이너: kafka:29092 (환경변수로 override)
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_request_topic: str = "rag.embeddings.request"
    kafka_status_topic: str = "rag.embeddings.status"
    kafka_consumer_group: str = "embedding-worker-group"
    
    # Kafka SASL 인증 (운영 환경)
    kafka_security_protocol: str = "PLAINTEXT"  # 로컬: PLAINTEXT, 운영: SASL_PLAINTEXT
    kafka_sasl_mechanism: str = "SCRAM-SHA-256"
    kafka_sasl_username: str = ""
    kafka_sasl_password: str = ""
    
    # ============================================
    # MinIO 설정
    # ============================================
    # 로컬 개발: localhost:9000 (기본값)
    # Docker 컨테이너: minio:9000 (환경변수로 override)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "rag"  # 단일 버킷 사용
    
    # ============================================
    # Qdrant 설정
    # ============================================
    # 로컬 개발: localhost:6333 (기본값)
    # Docker 컨테이너: qdrant:6333 (환경변수로 override)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "rag_chunks_v1"
    qdrant_collection_hybrid: str = "rag_chunks_v2"  # 하이브리드(dense+sparse) 컬렉션
    qdrant_vector_size: int = 1024  # BGE-M3 기본 차원

    # BGE-M3 임베딩 API (보조 GPU 서버 TEI)
    # 컨테이너 내부에서 모델을 직접 로드하지 않고, 원격 API를 호출합니다.
    bge_m3_api_url: str = "http://localhost:4000/v1/embeddings"
    bge_m3_api_key: str = ""
    bge_m3_model_name: str = "embed-bge-m3"
    bge_m3_model_path: str = "http://localhost:4000/v1/embeddings"  # API 엔드포인트 (통계 기록용)
    # batch_size: 한 번에 BGE-M3 API로 전송할 청크 수.
    # 너무 크면 게이트웨이 413 (Content Too Large) 에러 발생 (특히 OCR 청크처럼 토큰이 큰 경우).
    bge_m3_batch_size: int = 5
    bge_m3_timeout_seconds: int = 60

    # BGE-M3 하이브리드 임베딩 API (FlagEmbedding 직접 서빙 - dense + sparse 동시 반환)
    bge_m3_hybrid_api_url: str = "http://localhost:8012/embed_all"
    bge_m3_hybrid_batch_size: int = 20
    bge_m3_hybrid_timeout_seconds: int = 60

    # ============================================
    # OCR Provider — Nemotron OCR v2 고정 (강제)
    # ============================================
    # 정책: 무조건 Nemotron만 사용. 다른 OCR(Gemma/Tesseract/PaddleOCR 등) 금지.
    # 환경변수로도 전환 불가 — 워커 코드에서 NemotronOCRClient 직접 호출.

    # ============================================
    # Nemotron OCR v2 (FastAPI, scripts/nemotron_server.py)
    # ============================================
    nemotron_ocr_host: str = "127.0.0.1"
    nemotron_ocr_port: int = 8002
    nemotron_ocr_timeout_seconds: int = 300
    # 페이지 내 신뢰도 낮은 영역 자동 재추론 임계값 (메모리 결정값: 0.80)
    nemotron_ocr_retry_threshold: float = 0.80
    # 재추론 시 영역 확대 배율 (메모리 결정값: 2.0)
    nemotron_ocr_retry_upscale: float = 2.0
    # 검출 결과 병합 단위: word | sentence | paragraph
    nemotron_ocr_merge_level: str = "paragraph"
    # GPU 동시성 제한 — 검색·답변 응답 보호 우선 (1=직렬)
    nemotron_ocr_max_concurrency: int = 1

    # OCR 페이지 판정 임계값
    # 페이지 텍스트가 N자 미만이고 이미지/도형이 있으면 페이지 통째 OCR로 처리.
    # N자 이상이면 PyMuPDF 텍스트 추출 + 이미지 객체별 OCR(옵션 A).
    ocr_page_text_threshold: int = 50
    # 텍스트레이어 corruption 게이트: get_text() 결과의 quality_score corruption 점수가
    # 이 값 이상이면 임베디드 폰트(ToUnicode CMap) 손상으로 판정 → 텍스트레이어 폐기,
    # 페이지 통째 OCR 폴백. 실측: 정상 페이지=0, 깨진 페이지=37~47 → 6이면 안전히 분리.
    ocr_text_layer_corruption_gate: int = 6
    # 페이지 통째 렌더링 시 PNG 해상도 배율 (낮추면 GPU 부하·속도 ↓, 정확도도 ↓)
    ocr_render_scale: float = 2.0
    # 이미지 객체별 OCR(옵션 A) — 작은 이미지는 Lanczos로 upscale 후 OCR.
    # max(width, height) 가 이 값 미만이면 upscale_factor 배 확대.
    # 예: 600x400 이미지 + threshold=1500 → 2배 upscale → 1200x800
    # 1500px 이상의 큰 이미지(페이지 스캔본 등)는 그대로 전송 — GPU 부하 보호
    # 및 어차피 모델이 downsampling하므로 효과 미미.
    ocr_image_upscale_threshold_px: int = 1500
    ocr_image_upscale_factor: float = 2.0

    # CASE 1(텍스트≥threshold) 페이지에 raster 이미지는 없지만 vector path 도형이 많으면
    # 페이지 통째 OCR을 추가로 호출해 도면 안 글자를 캡처한다.
    # PowerPoint/Visio→PDF 변환 시 도면이 vector로 박혀 page.get_images()에 안 잡히는 케이스 대응.
    # imgs==0 AND drawings > threshold 일 때만 트리거 (이미지 OCR과 중복 방지).
    ocr_page_drawings_threshold: int = 50

    # 임베딩 프로필 → 버전/컬렉션 매핑
    embedding_profile_v1: str = "bge_m3_v1"
    embedding_profile_hybrid: str = "bge_m3_hybrid_v2"

    # 임베딩 버전 관리
    embedding_version: str = "bge-m3-v1"  # 임베딩 버전 (모델 변경 시 v2, v3 등으로 증가)
    embedding_version_hybrid: str = "bge-m3-hybrid-v2"  # 하이브리드 버전
    
    # 재시도 설정
    max_retry_count: int = 3
    retry_delay_seconds: float = 1.0
    job_max_retries: int = 3  # 임베딩 Job 최대 재시도 횟수
    
    # ============================================
    # 중복 검사 설정
    # ============================================
    duplicate_sample_size: int = 10  # 중복 검사 시 샘플링할 청크 개수
    duplicate_similarity_threshold: float = 0.85  # 개별 청크 유사도 임계값 (85%)
    duplicate_match_ratio: float = 0.6  # 매칭 비율 임계값 (60% 이상 매칭 시 중복)
    
    # ============================================
    # 문서 파일 처리 설정
    # ============================================
    # use_libreoffice: True이면 LibreOffice로 PDF 변환 후 추출 (페이지 정보 포함, 권장)
    # False이면 각 라이브러리로 직접 추출 (페이지 정보 없음, 빠름)
    # 적용 대상: DOC, DOCX (HWP/HWPX는 항상 원본 파싱 사용)
    use_libreoffice: bool = True  # 운영 서버 권장 (DOC/DOCX 페이지 정보 필수)
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "allow"  # 추가 속성 허용
    }


# 전역 설정 인스턴스
settings = Settings()

