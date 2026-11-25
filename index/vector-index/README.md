# RAG Embedding Pipeline

DY sLLM 시스템의 문서 임베딩 파이프라인입니다.
임베딩 요청을 받으면 텍스트 추출, 청킹, 벡터 임베딩 생성까지 자동으로 처리합니다.

## 아키텍처

```
클라이언트 → ER Server (FastAPI) → Kafka → EW Worker → Qdrant
                  ↕                           ↕    ↕
              PostgreSQL                  PostgreSQL / MinIO / BGE-M3
```

- **ER (Embedding Request Server)** — 임베딩 요청 접수, 중복 체크, Kafka 발행
- **EW (Embedding Worker)** — 텍스트 추출 → 청킹 → 임베딩 → 벡터DB 저장

## 기술 스택

| 구분 | 기술 |
|------|------|
| API 서버 | FastAPI, uvicorn |
| 메시지 큐 | Apache Kafka |
| 데이터베이스 | PostgreSQL (SQLAlchemy) |
| 벡터 DB | Qdrant (1024차원, 코사인 유사도) |
| 파일 저장소 | MinIO (S3 호환) |
| 임베딩 모델 | BGE-M3 (원격 API) |
| 컨테이너 | Docker, Docker Compose |

## 지원 파일 형식

PDF, DOCX, DOC, PPTX, PPT, XLSX, XLSM, XLS, CSV, HWP, HWPX, TXT

## 프로젝트 구조

```
rag-embedding-pipeline/
├── api/            # ER HTTP 엔드포인트
├── workers/        # EW Kafka consumer
├── chunking/       # 텍스트 추출 + 청킹
├── embeddings/     # BGE-M3 API 클라이언트
├── storage/        # MinIO, Qdrant 클라이언트
├── db/             # PostgreSQL 연결, Repository, 마이그레이션
├── models/         # ORM 모델, DTO, Enum
├── kafka_client/   # Kafka Producer/Consumer
├── utils/          # 로깅, JSON 유틸리티
├── scripts/        # 헬퍼 스크립트
└── config.py       # 환경변수 기반 설정
```

## 빠른 시작

### 설치

```bash
pip install -r requirements.txt
```

### 실행

```bash
# ER 서버
uvicorn api.er_server:app --host 0.0.0.0 --port 8100

# EW 워커
python -m workers.embedding_worker
```

### Docker

```bash
# 개발 환경
docker compose -f docker-compose.dev-er.yml up -d
docker compose -f docker-compose.dev-ew.yml up -d

# 운영 환경
docker compose -f docker-compose.prod-er.yml up -d
docker compose -f docker-compose.prod-ew.yml up -d
```

## 문서

상세 가이드는 [docs/](docs/) 폴더를 참고하세요.
