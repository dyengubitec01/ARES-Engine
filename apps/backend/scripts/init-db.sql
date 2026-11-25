-- ============================================================
-- DY-OOO AI 솔루션 Database DDL
-- Version: 0.5
-- Date: 2026.05.27
-- Database: PostgreSQL
-- Schema: rag (스키마는 사전에 수동 생성 필요)
-- ============================================================

-- ============================================================
-- 스키마 설정 (스키마는 미리 생성되어 있어야 함)
-- ⚠️ 운영(prod): SET search_path TO rag;
-- ⚠️ 개발(dev):  SET search_path TO rag_dev;
-- ============================================================
SET search_path TO rag;

-- ============================================================
-- 기존 테이블 삭제 (역순으로 삭제 - FK 의존성 고려)
-- ============================================================
--
-- ⚠️ 문서 삭제: DB 레벨 ON DELETE CASCADE 적용
-- doc_documents 삭제 시 관련 테이블 자동 삭제됨
--
-- Note: MinIO 파일은 DeleteObject 권한 없음으로 삭제 불가 (관리자 별도 정리 필요)
-- ============================================================

DROP TABLE IF EXISTS chat_document_reference CASCADE;
DROP TABLE IF EXISTS chat_interaction CASCADE;
DROP TABLE IF EXISTS chat_session CASCADE;
DROP TABLE IF EXISTS auth_users_login_history CASCADE;
DROP TABLE IF EXISTS auth_users_alarm CASCADE;
DROP TABLE IF EXISTS storage_object_files CASCADE;
DROP TABLE IF EXISTS rag_processing_stats CASCADE;
DROP TABLE IF EXISTS rag_similarity_checks CASCADE;
DROP TABLE IF EXISTS rag_upsert_history CASCADE;
DROP TABLE IF EXISTS rag_embeddings_index CASCADE;
DROP TABLE IF EXISTS vec_qdrant_collections CASCADE;
DROP TABLE IF EXISTS rag_chunks CASCADE;
DROP TABLE IF EXISTS rag_status_events CASCADE;
DROP TABLE IF EXISTS rag_embedding_jobs CASCADE;
DROP TABLE IF EXISTS doc_user_tag_mappings CASCADE;
DROP TABLE IF EXISTS doc_user_tags CASCADE;
DROP TABLE IF EXISTS doc_embed_review CASCADE;
DROP TABLE IF EXISTS doc_document_exclude CASCADE;
DROP TABLE IF EXISTS doc_document_favorites CASCADE;
DROP TABLE IF EXISTS auth_users_dept_authority_permission CASCADE;
DROP TABLE IF EXISTS doc_document_content CASCADE;
DROP TABLE IF EXISTS doc_documents CASCADE;
DROP TABLE IF EXISTS auth_users_authority_permission CASCADE;
DROP TABLE IF EXISTS auth_users_authority CASCADE;
DROP TABLE IF EXISTS auth_users CASCADE;
DROP TABLE IF EXISTS auth_users_dept CASCADE;
DROP TABLE IF EXISTS board_surveys CASCADE;
DROP TABLE IF EXISTS board_post_adoptions CASCADE;
DROP TABLE IF EXISTS board_comments CASCADE;
DROP TABLE IF EXISTS board_post_images CASCADE;
DROP TABLE IF EXISTS board_posts CASCADE;
DROP TABLE IF EXISTS board_types CASCADE;

-- ============================================================
-- 기존 ENUM 타입 삭제
-- ============================================================

DROP TYPE IF EXISTS authority_type CASCADE;
DROP TYPE IF EXISTS board_type_name CASCADE;
DROP TYPE IF EXISTS doc_status CASCADE;
DROP TYPE IF EXISTS job_status CASCADE;
DROP TYPE IF EXISTS event_source CASCADE;
DROP TYPE IF EXISTS object_kind CASCADE;
DROP TYPE IF EXISTS distance_metric CASCADE;

-- ============================================================
-- ENUM 타입 정의
-- ============================================================

CREATE TYPE authority_type AS ENUM ('uploader', 'admin', 'embedding', 'download', 'soft_delete');
CREATE TYPE board_type_name AS ENUM ('feedback', 'notice', 'suggestion', 'answer_suggestion');
CREATE TYPE doc_status AS ENUM ('uploading', 'uploaded', 'validating', 'queued', 'parsing', 'chunking', 'embedding', 'upserting', 'completed', 'failed', 'deleted', 'pending_approval', 'rejected');
CREATE TYPE job_status AS ENUM ('queued', 'processing', 'completed', 'failed', 'embedding', 'upserting', 'done', 'success', 'started');
CREATE TYPE event_source AS ENUM ('er', 'ew', 'be', 'system');
CREATE TYPE object_kind AS ENUM ('raw', 'chunks', 'embeddings', 'meta', 'manifest', 'metadata', 'stats', 'logs', 'chunks_metadata');
CREATE TYPE distance_metric AS ENUM ('cosine', 'euclidean', 'dot');

-- ============================================================
-- 1. auth_users_dept (조직/부서)
-- 설명: 유저의 조직 관리 테이블
-- ============================================================

CREATE TABLE auth_users_dept (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dept_name       VARCHAR(100) NOT NULL DEFAULT '기술연구소',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE auth_users_dept IS '유저의 조직 관리 테이블';
COMMENT ON COLUMN auth_users_dept.id IS '조직 고유 ID(UUID)';
COMMENT ON COLUMN auth_users_dept.dept_name IS '조직 이름 (부문은 고려하지 않았음)';
COMMENT ON COLUMN auth_users_dept.created_at IS '조직 이름 생성 시각';

-- 기본 부서 데이터 삽입
INSERT INTO auth_users_dept (id, dept_name) VALUES
    ('00000000-0000-0000-0000-000000000001', '기술연구소');

-- ============================================================
-- 2. auth_users (사용자 계정 정보)
-- 설명: LLM 시스템을 사용하는 사용자 계정을 관리
-- 권한은 auth_users_authority_permission 테이블로 관리
-- ============================================================

CREATE TABLE auth_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(320) NOT NULL UNIQUE,
    name            VARCHAR(100),
    auth_dept_id    UUID REFERENCES auth_users_dept(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    job_title       VARCHAR(100) DEFAULT NULL
);

COMMENT ON TABLE auth_users IS 'LLM 시스템을 사용하는 사용자 계정을 관리. 권한은 auth_users_authority_permission으로 관리';
COMMENT ON COLUMN auth_users.id IS '시스템 내부 사용자 고유 식별자(UUID)';
COMMENT ON COLUMN auth_users.email IS '로그인용 이메일 주소(유니크)';
COMMENT ON COLUMN auth_users.name IS '사용자 이름(표시 목적)';
COMMENT ON COLUMN auth_users.auth_dept_id IS '사용자 부서 (Graph API에서 동기화, nullable)';
COMMENT ON COLUMN auth_users.created_at IS '사용자 생성 시각';
COMMENT ON COLUMN auth_users.job_title IS 'Azure AD Graph API에서 동기화된 직책';

-- ============================================================
-- 3. auth_users_authority (권한)
-- 설명: 시스템 기본 권한 테이블
-- ============================================================

CREATE TABLE auth_users_authority (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    authority_name  authority_type NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE auth_users_authority IS '시스템 기본 권한 테이블 (uploader, admin, embedding, download, soft_delete)';
COMMENT ON COLUMN auth_users_authority.id IS '권한 고유(UUID)';
COMMENT ON COLUMN auth_users_authority.authority_name IS '권한 타입';
COMMENT ON COLUMN auth_users_authority.created_at IS '권한 생성 시각';

-- 기본 권한 데이터 삽입
INSERT INTO auth_users_authority (id, authority_name) VALUES
    ('00000000-0000-0000-0000-000000000010', 'uploader'),
    ('00000000-0000-0000-0000-000000000020', 'admin'),
    ('00000000-0000-0000-0000-000000000040', 'embedding'),
    ('00000000-0000-0000-0000-000000000050', 'soft_delete'),
    ('00000000-0000-0000-0000-000000000060', 'download');

-- ============================================================
-- 4. auth_users_authority_permission (권한 내역)
-- 설명: 유저가 가진 권한들을 관리하는 테이블
-- ============================================================

CREATE TABLE auth_users_authority_permission (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    authority_id    UUID NOT NULL REFERENCES auth_users_authority(id),
    users_id        UUID NOT NULL REFERENCES auth_users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (authority_id, users_id)
);

COMMENT ON TABLE auth_users_authority_permission IS '유저가 가진 권한들을 관리하는 테이블';
COMMENT ON COLUMN auth_users_authority_permission.id IS '유저 권한 내역 고유(UUID)';
COMMENT ON COLUMN auth_users_authority_permission.authority_id IS '유저 권한 테이블 ID 외래키';
COMMENT ON COLUMN auth_users_authority_permission.users_id IS '유저 테이블 ID 외래키';
COMMENT ON COLUMN auth_users_authority_permission.created_at IS '유저 권한 내역 생성 시각';

-- ============================================================
-- 5. doc_documents (문서 전역 식별자)
-- 설명: "문서"라는 개념의 최상위 ID를 관리
-- ============================================================

CREATE TABLE doc_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT,
    minio_url       VARCHAR NOT NULL,
    created_by      UUID NOT NULL REFERENCES auth_users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE doc_documents IS '"문서"라는 개념의 최상위 ID를 관리';
COMMENT ON COLUMN doc_documents.id IS '문서 전역 식별자';
COMMENT ON COLUMN doc_documents.title IS '문서 제목 또는 추출된 제목';
COMMENT ON COLUMN doc_documents.minio_url IS 'MinIO에 저장할 경로';
COMMENT ON COLUMN doc_documents.created_by IS '문서를 최초 업로드한 사용자';
COMMENT ON COLUMN doc_documents.created_at IS '문서 최초 생성 시각';

-- ============================================================
-- 6. doc_document_content (문서 버전/상태)
-- 설명: 각 문서의 버전별 정보와 처리 상태를 관리
-- ============================================================

CREATE TABLE doc_document_content (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES doc_documents(id) ON DELETE CASCADE,
    version_no          INTEGER NOT NULL,
    original_filename   TEXT NOT NULL,
    uploader_id         UUID NOT NULL,
    auth_dept_id        UUID,
    sha256              CHAR(64) UNIQUE,
    file_size           BIGINT NOT NULL,
    mime_type           TEXT NOT NULL,
    language            TEXT,
    encoding            TEXT,
    status              doc_status NOT NULL DEFAULT 'uploaded',
    status_reason       TEXT,
    status_message      TEXT,
    requested_at        TIMESTAMP,
    queued_at           TIMESTAMPTZ,
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    file_modified_at    TIMESTAMPTZ NOT NULL,
    deleted_at          TIMESTAMPTZ,
    is_active           CHAR(1) NOT NULL DEFAULT 'Y'
);

COMMENT ON TABLE doc_document_content IS '각 문서의 버전별 정보와 처리 상태를 관리';
COMMENT ON COLUMN doc_document_content.id IS '문서 버전별 고유 식별자(UUID)';
COMMENT ON COLUMN doc_document_content.document_id IS '문서의 상위 원본 ID';
COMMENT ON COLUMN doc_document_content.version_no IS '문서의 버전 번호(1부터 증가)';
COMMENT ON COLUMN doc_document_content.original_filename IS '업로드 당시 파일명';
COMMENT ON COLUMN doc_document_content.uploader_id IS '파일 업로드한 사용자';
COMMENT ON COLUMN doc_document_content.auth_dept_id IS '업로드 사용자의 부서 ID (auth_users_dept FK)';
COMMENT ON COLUMN doc_document_content.sha256 IS '원본 파일의 SHA-256 해시(중복 판정)';
COMMENT ON COLUMN doc_document_content.file_size IS '파일 크기(byte)';
COMMENT ON COLUMN doc_document_content.mime_type IS '파일 MIME 타입';
COMMENT ON COLUMN doc_document_content.language IS '문서 언어(ko/en 등)';
COMMENT ON COLUMN doc_document_content.encoding IS '파일의 문자 인코딩(UTF-8 등)';
COMMENT ON COLUMN doc_document_content.status IS '파이프라인 처리 상태';
COMMENT ON COLUMN doc_document_content.status_reason IS '상태 변경 사유 또는 오류 요약';
COMMENT ON COLUMN doc_document_content.status_message IS '상태 관련 메시지';
COMMENT ON COLUMN doc_document_content.requested_at IS '임베딩 요청 시각';
COMMENT ON COLUMN doc_document_content.queued_at IS '임베딩 큐에 등록된 시각';
COMMENT ON COLUMN doc_document_content.started_at IS '파이프라인 처리 시작 시각';
COMMENT ON COLUMN doc_document_content.finished_at IS '파이프라인 처리 완료 시각';
COMMENT ON COLUMN doc_document_content.created_at IS '레코드 생성 시각';
COMMENT ON COLUMN doc_document_content.updated_at IS '레코드 수정 시각';
COMMENT ON COLUMN doc_document_content.file_modified_at IS '중복 방지를 위한 파일 수정일자 체크';
COMMENT ON COLUMN doc_document_content.deleted_at IS 'Soft Delete 시각 (NULL이면 삭제 안됨)';
COMMENT ON COLUMN doc_document_content.is_active IS 'MinIO 메타데이터 활성 상태 (Y: 활성, N: 비활성/삭제됨)';

-- ============================================================
-- 7. auth_users_dept_authority_permission (사용자-부서 권한 매핑)
-- 설명: 사용자별 부서 권한 다대다 매핑 테이블
-- ============================================================

CREATE TABLE auth_users_dept_authority_permission (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    users_id        UUID NOT NULL REFERENCES auth_users(id),
    dept_id         UUID NOT NULL REFERENCES auth_users_dept(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (users_id, dept_id)
);

COMMENT ON TABLE auth_users_dept_authority_permission IS '사용자별 부서 권한 다대다 매핑 테이블';
COMMENT ON COLUMN auth_users_dept_authority_permission.id IS '부서 권한 매핑 고유(UUID)';
COMMENT ON COLUMN auth_users_dept_authority_permission.users_id IS '사용자 테이블 ID 외래키';
COMMENT ON COLUMN auth_users_dept_authority_permission.dept_id IS '조직 테이블 ID 외래키';
COMMENT ON COLUMN auth_users_dept_authority_permission.created_at IS '부서 권한 매핑 생성 시각';

-- ============================================================
-- 8. doc_document_favorites (문서 즐겨찾기)
-- 설명: 유저의 문서 즐겨찾기
-- ============================================================

CREATE TABLE doc_document_favorites (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES doc_documents(id) ON DELETE CASCADE,
    users_id        UUID NOT NULL REFERENCES auth_users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE doc_document_favorites IS '유저의 문서 즐겨찾기';
COMMENT ON COLUMN doc_document_favorites.id IS '문서 즐겨 찾기 ID(UUID)';
COMMENT ON COLUMN doc_document_favorites.document_id IS '문서 ID 외래키';
COMMENT ON COLUMN doc_document_favorites.users_id IS '유저 ID 외래키';
COMMENT ON COLUMN doc_document_favorites.created_at IS '즐겨찾기 생성 시각';

-- ============================================================
-- 8-1. doc_user_tags (사용자 개인 문서 태그 정의)
-- 설명: 사용자가 자신의 문서 분류를 위해 만든 태그 (이름 + 컬러)
--       태그는 사용자별 개인 소유, 같은 이름이어도 사용자 간 별개
-- ============================================================

CREATE TABLE doc_user_tags (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    name            VARCHAR(50) NOT NULL,
    color           VARCHAR(20) NOT NULL DEFAULT '#9e9e9e',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);

COMMENT ON TABLE doc_user_tags IS '사용자별 개인 문서 분류 태그';
COMMENT ON COLUMN doc_user_tags.id IS '태그 고유 ID(UUID)';
COMMENT ON COLUMN doc_user_tags.user_id IS '태그 소유자 (auth_users FK, CASCADE)';
COMMENT ON COLUMN doc_user_tags.name IS '태그 이름 (사용자 내 UNIQUE)';
COMMENT ON COLUMN doc_user_tags.color IS '태그 표시 색상 (#RRGGBB)';
COMMENT ON COLUMN doc_user_tags.created_at IS '태그 생성 시각';
COMMENT ON COLUMN doc_user_tags.updated_at IS '태그 수정 시각';

-- ============================================================
-- 8-2. doc_user_tag_mappings (문서-태그 매핑)
-- 설명: 사용자가 문서에 부여한 개인 태그 매핑 (N:M)
--       다른 사용자에게는 노출되지 않음
-- ============================================================

CREATE TABLE doc_user_tag_mappings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    tag_id          UUID NOT NULL REFERENCES doc_user_tags(id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES doc_documents(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, tag_id, document_id)
);

COMMENT ON TABLE doc_user_tag_mappings IS '사용자가 문서에 부여한 개인 태그 매핑 (N:M)';
COMMENT ON COLUMN doc_user_tag_mappings.id IS '매핑 고유 ID(UUID)';
COMMENT ON COLUMN doc_user_tag_mappings.user_id IS '태그 소유자 (auth_users FK, CASCADE)';
COMMENT ON COLUMN doc_user_tag_mappings.tag_id IS '태그 ID (doc_user_tags FK, CASCADE)';
COMMENT ON COLUMN doc_user_tag_mappings.document_id IS '문서 ID (doc_documents FK, CASCADE)';
COMMENT ON COLUMN doc_user_tag_mappings.created_at IS '매핑 생성 시각';

-- ============================================================
-- 9-1. doc_document_exclude (문서 RAG 참조 제외)
-- 설명: 사용자가 특정 문서 버전을 RAG 참조에서 제외한 목록
--       레코드 있음 = OFF(제외), 레코드 없음 = ON(참조 가능, 기본값)
-- ============================================================

CREATE TABLE doc_document_exclude (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_content_id UUID NOT NULL REFERENCES doc_document_content(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, document_content_id)
);

COMMENT ON TABLE doc_document_exclude IS '사용자별 RAG 참조 제외 문서 버전 목록 (레코드 있음=OFF, 없음=ON)';
COMMENT ON COLUMN doc_document_exclude.id IS '제외 레코드 ID(UUID)';
COMMENT ON COLUMN doc_document_exclude.document_content_id IS '문서 버전 ID (doc_document_content FK, CASCADE)';
COMMENT ON COLUMN doc_document_exclude.user_id IS '사용자 ID (auth_users FK, CASCADE)';
COMMENT ON COLUMN doc_document_exclude.created_at IS '제외 설정 시각';

-- ============================================================
-- 9-2. doc_embed_review (임베딩 검토/승인)
-- 설명: 문서 임베딩 검토 및 승인/반려 기록
-- ============================================================

CREATE TABLE doc_embed_review (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_content_id  UUID NOT NULL REFERENCES doc_document_content(id) ON DELETE CASCADE,
    reviewer_id     UUID NOT NULL REFERENCES auth_users(id),
    action          VARCHAR(10) NOT NULL,
    reason          VARCHAR(500),
    created_at      TIMESTAMP DEFAULT now()
);

-- ============================================================
-- 9. rag_embedding_jobs (임베딩 Job / Kafka 연동)
-- 설명: BE/ER에서 생성해 Kafka로 발행하는 임베딩 작업 단위(Job)를 관리
-- ============================================================

CREATE TABLE rag_embedding_jobs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_content_id          UUID NOT NULL REFERENCES doc_document_content(id) ON DELETE CASCADE,
    kafka_topic             VARCHAR(100) NOT NULL,
    kafka_key               VARCHAR(200) NOT NULL,
    partition               INTEGER,
    "offset"                BIGINT,
    priority                INTEGER NOT NULL DEFAULT 0,
    retry_count             INTEGER NOT NULL DEFAULT 0,
    payload_json            JSON,
    status                  job_status NOT NULL DEFAULT 'queued',
    enqueued_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at              TIMESTAMPTZ,
    finished_at             TIMESTAMPTZ,
    minio_original_filename VARCHAR(255),
    minio_mime_type         VARCHAR(128),
    minio_file_size         BIGINT,
    worker_id               VARCHAR(100),
    error_message           TEXT
);

COMMENT ON TABLE rag_embedding_jobs IS 'BE/ER에서 생성해 Kafka로 발행하는 임베딩 작업 단위(Job)를 관리';
COMMENT ON COLUMN rag_embedding_jobs.id IS '임베딩 작업(Job)의 고유 ID';
COMMENT ON COLUMN rag_embedding_jobs.doc_content_id IS '임베딩 대상 문서 버전';
COMMENT ON COLUMN rag_embedding_jobs.kafka_topic IS '메시지가 발행된 Kafka 토픽명';
COMMENT ON COLUMN rag_embedding_jobs.kafka_key IS 'Kafka 메시지 키';
COMMENT ON COLUMN rag_embedding_jobs.partition IS 'Kafka 파티션 번호';
COMMENT ON COLUMN rag_embedding_jobs."offset" IS 'Kafka 메시지 오프셋';
COMMENT ON COLUMN rag_embedding_jobs.priority IS '처리 우선순위(값이 작을수록 우선)';
COMMENT ON COLUMN rag_embedding_jobs.retry_count IS '실패 후 재시도 횟수';
COMMENT ON COLUMN rag_embedding_jobs.payload_json IS 'Kafka 발행 당시의 원본 payload';
COMMENT ON COLUMN rag_embedding_jobs.status IS 'Job 처리 상태';
COMMENT ON COLUMN rag_embedding_jobs.enqueued_at IS 'Job 큐에 등록된 시간';
COMMENT ON COLUMN rag_embedding_jobs.started_at IS '워커가 Job 실행을 시작한 시간';
COMMENT ON COLUMN rag_embedding_jobs.finished_at IS 'Job 처리 완료 시간';
COMMENT ON COLUMN rag_embedding_jobs.minio_original_filename IS 'MinIO 업로드 시 사용된 원본 파일명';
COMMENT ON COLUMN rag_embedding_jobs.minio_mime_type IS 'MinIO 오브젝트의 MIME(Content-Type)';
COMMENT ON COLUMN rag_embedding_jobs.minio_file_size IS 'MinIO 오브젝트의 파일 크기(byte)';
COMMENT ON COLUMN rag_embedding_jobs.worker_id IS 'Job을 처리한 워커 식별자';
COMMENT ON COLUMN rag_embedding_jobs.error_message IS 'Job 실패 시 오류 내용';

-- ============================================================
-- 10. rag_status_events (문서 버전 상태 이벤트 로그)
-- 설명: 문서 버전 단위로 발생하는 상태 변경 이벤트 로그(append-only)
-- ============================================================

CREATE TABLE rag_status_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_content_id  UUID NOT NULL REFERENCES doc_document_content(id) ON DELETE CASCADE,
    job_id          UUID REFERENCES rag_embedding_jobs(id) ON DELETE CASCADE,
    source          event_source NOT NULL,
    category        VARCHAR(32) NOT NULL DEFAULT 'job',
    message         TEXT,
    metadata        JSONB,
    status          TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE rag_status_events IS '문서 버전 단위로 발생하는 상태 변경 이벤트 로그(append-only)';
COMMENT ON COLUMN rag_status_events.id IS '상태 변경 이벤트 고유 ID';
COMMENT ON COLUMN rag_status_events.doc_content_id IS '이벤트가 발생한 문서 버전';
COMMENT ON COLUMN rag_status_events.job_id IS '해당 이벤트가 속한 임베딩 Job 식별자';
COMMENT ON COLUMN rag_status_events.source IS '이벤트를 생성한 컴포넌트 식별값 (er, ew, be, system)';
COMMENT ON COLUMN rag_status_events.category IS '이벤트 종류(job, chunk 등)';
COMMENT ON COLUMN rag_status_events.message IS '상태 이벤트에 대한 설명 메시지';
COMMENT ON COLUMN rag_status_events.metadata IS '이벤트 관련 부가 정보(JSON)';
COMMENT ON COLUMN rag_status_events.status IS '변경된 상태명';
COMMENT ON COLUMN rag_status_events.created_at IS '이벤트 생성 시각';

-- ============================================================
-- 11. rag_chunks (텍스트 청크 정의)
-- 설명: 파싱된 문서를 여러 청크로 나눈 결과를 관리
-- ============================================================

CREATE TABLE rag_chunks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_content_id      UUID NOT NULL REFERENCES doc_document_content(id) ON DELETE CASCADE,
    chunk_index         INTEGER NOT NULL,
    ref_hash            VARCHAR(128),
    text                TEXT,
    text_checksum       VARCHAR(64),
    page_start          INTEGER,
    page_end            INTEGER,
    sheet_name          VARCHAR(255),
    row_start           INTEGER,
    row_end             INTEGER,
    metadata            JSONB,
    start_char          INTEGER,
    end_char            INTEGER,
    token_count         INTEGER NOT NULL,
    text_hash           CHAR(64) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedding_version   VARCHAR(64) NOT NULL DEFAULT 'bge-m3-v1',
    extraction_version  VARCHAR(64),
    UNIQUE (doc_content_id, chunk_index)
);

COMMENT ON TABLE rag_chunks IS '파싱된 문서를 여러 청크로 나눈 결과를 관리';
COMMENT ON COLUMN rag_chunks.id IS 'rag_chunks 레코드의 기본 키. 자동 UUID 생성';
COMMENT ON COLUMN rag_chunks.doc_content_id IS '청크가 속한 문서 버전';
COMMENT ON COLUMN rag_chunks.chunk_index IS '문서 내 청크 인덱스(0 또는 1부터 시작)';
COMMENT ON COLUMN rag_chunks.ref_hash IS '원본 텍스트 또는 전처리 레퍼런스의 식별 해시';
COMMENT ON COLUMN rag_chunks.text IS '분할된 문서 청크의 원문 텍스트 전체를 저장';
COMMENT ON COLUMN rag_chunks.text_checksum IS '청크 텍스트에 대한 SHA-256 해시값';
COMMENT ON COLUMN rag_chunks.page_start IS '청크가 속한 문서 내 시작 페이지 번호';
COMMENT ON COLUMN rag_chunks.page_end IS '청크가 속한 문서 내 종료 페이지 번호';
COMMENT ON COLUMN rag_chunks.sheet_name IS 'XLSX 문서 처리 시 청크가 속한 시트(sheet) 이름';
COMMENT ON COLUMN rag_chunks.row_start IS 'XLSX 문서 처리 시 청크가 속한 시트 내 시작 행 번호';
COMMENT ON COLUMN rag_chunks.row_end IS 'XLSX 문서 처리 시 청크가 속한 시트 내 종료 행 번호';
COMMENT ON COLUMN rag_chunks.metadata IS '청크 생성 시 부가 정보 저장용 JSON';
COMMENT ON COLUMN rag_chunks.start_char IS '원문에서 시작 문자 위치';
COMMENT ON COLUMN rag_chunks.end_char IS '원문에서 끝 문자 위치';
COMMENT ON COLUMN rag_chunks.token_count IS '청크의 토큰 개수';
COMMENT ON COLUMN rag_chunks.text_hash IS '청크 텍스트 SHA-256 해시';
COMMENT ON COLUMN rag_chunks.created_at IS '청크 생성 시간';
COMMENT ON COLUMN rag_chunks.embedding_version IS '임베딩 모델 버전';
COMMENT ON COLUMN rag_chunks.extraction_version IS '텍스트 추출 버전';

-- ============================================================
-- 12. vec_qdrant_collections (Qdrant 컬렉션 메타)
-- 설명: Qdrant에 존재하는 컬렉션에 대한 구성 정보 메타를 RDB에 복제해 관리
-- ============================================================

CREATE TABLE vec_qdrant_collections (
    name                VARCHAR(100) PRIMARY KEY,
    vector_dim          INTEGER NOT NULL,
    metric              distance_metric NOT NULL,
    shard_count         INTEGER NOT NULL,
    replication_factor  INTEGER NOT NULL,
    write_consistency   VARCHAR(20) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE vec_qdrant_collections IS 'Qdrant에 존재하는 컬렉션에 대한 구성 정보 메타를 RDB에 복제해 관리';
COMMENT ON COLUMN vec_qdrant_collections.name IS 'Qdrant 컬렉션 이름(고유)';
COMMENT ON COLUMN vec_qdrant_collections.vector_dim IS '해당 컬렉션 벡터 차원';
COMMENT ON COLUMN vec_qdrant_collections.metric IS 'Qdrant 유사도 계산 방식';
COMMENT ON COLUMN vec_qdrant_collections.shard_count IS 'Qdrant 샤드 개수';
COMMENT ON COLUMN vec_qdrant_collections.replication_factor IS '데이터 복제본 개수';
COMMENT ON COLUMN vec_qdrant_collections.write_consistency IS 'Qdrant 쓰기 일관성 모드';
COMMENT ON COLUMN vec_qdrant_collections.created_at IS '생성 시각';
COMMENT ON COLUMN vec_qdrant_collections.updated_at IS '수정 시각';

-- ============================================================
-- 13. rag_embeddings_index (Qdrant 매핑/유효 인덱스)
-- 설명: 각 청크(chunk_id)가 Qdrant에 어떤 컬렉션/point_id로 저장돼 있는지를 매핑
-- ============================================================

CREATE TABLE rag_embeddings_index (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_content_id          UUID NOT NULL REFERENCES doc_document_content(id) ON DELETE CASCADE,
    chunk_id                UUID NOT NULL REFERENCES rag_chunks(id) ON DELETE CASCADE,
    chunk_index             INTEGER NOT NULL,
    qdrant_point_id         VARCHAR(128) NOT NULL,
    qdrant_collection_name  VARCHAR(100) NOT NULL REFERENCES vec_qdrant_collections(name),
    qdrant_vector_checksum  VARCHAR(128),
    qdrant_payload_checksum VARCHAR(128),
    vector_dim              INTEGER NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ,
    embedding_version       VARCHAR(64) NOT NULL DEFAULT 'bge-m3-v1',
    UNIQUE (doc_content_id, chunk_index, embedding_version)
);

COMMENT ON TABLE rag_embeddings_index IS '각 청크(chunk_id)가 Qdrant에 어떤 컬렉션/point_id로 저장돼 있는지를 매핑';
COMMENT ON COLUMN rag_embeddings_index.id IS '인덱스 레코드 PK (자동 생성)';
COMMENT ON COLUMN rag_embeddings_index.doc_content_id IS '인덱스가 속한 문서 버전 ID';
COMMENT ON COLUMN rag_embeddings_index.chunk_id IS '연동된 청크 ID';
COMMENT ON COLUMN rag_embeddings_index.chunk_index IS '문서 버전 내 청크 순번(0부터 시작)';
COMMENT ON COLUMN rag_embeddings_index.qdrant_point_id IS 'Qdrant에 저장된 벡터 포인트 식별자(ID)';
COMMENT ON COLUMN rag_embeddings_index.qdrant_collection_name IS 'Qdrant 컬렉션 이름';
COMMENT ON COLUMN rag_embeddings_index.qdrant_vector_checksum IS 'Qdrant 벡터 데이터에 대한 체크섬 값';
COMMENT ON COLUMN rag_embeddings_index.qdrant_payload_checksum IS 'Qdrant에 저장된 payload(JSON)의 체크섬';
COMMENT ON COLUMN rag_embeddings_index.vector_dim IS '임베딩 벡터의 차원';
COMMENT ON COLUMN rag_embeddings_index.created_at IS '레코드 생성 시각';
COMMENT ON COLUMN rag_embeddings_index.updated_at IS '레코드 최종 수정 시각';
COMMENT ON COLUMN rag_embeddings_index.embedding_version IS '임베딩 모델 버전';

-- ============================================================
-- 14. rag_upsert_history (Qdrant 업서트 시도 이력)
-- 설명: 각 청크에 대해 Qdrant 업서트를 몇 번 시도했고, 어떤 결과였는지를 기록
-- ============================================================

CREATE TABLE rag_upsert_history (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_content_id          UUID NOT NULL REFERENCES doc_document_content(id) ON DELETE CASCADE,
    chunk_id                UUID NOT NULL REFERENCES rag_chunks(id) ON DELETE CASCADE,
    job_id                  UUID NOT NULL REFERENCES rag_embedding_jobs(id) ON DELETE CASCADE,
    chunk_index             INTEGER NOT NULL,
    qdrant_collection_name  VARCHAR(255) NOT NULL,
    qdrant_point_id         VARCHAR(128) NOT NULL,
    vector_dim              INTEGER NOT NULL,
    status                  job_status NOT NULL,
    error_message           TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE rag_upsert_history IS '각 청크에 대해 Qdrant 업서트를 몇 번 시도했고, 어떤 결과였는지를 기록';
COMMENT ON COLUMN rag_upsert_history.id IS '업설트 이력 PK (자동생성)';
COMMENT ON COLUMN rag_upsert_history.doc_content_id IS '업설트 이력이 속한 문서 버전 ID';
COMMENT ON COLUMN rag_upsert_history.chunk_id IS '업서트 대상 청크의 식별자(UUID)';
COMMENT ON COLUMN rag_upsert_history.job_id IS '임베딩 작업 식별자(FK)';
COMMENT ON COLUMN rag_upsert_history.chunk_index IS '문서 내 청크 순번(0부터 시작하는 인덱스)';
COMMENT ON COLUMN rag_upsert_history.qdrant_collection_name IS 'Qdrant 컬렉션명';
COMMENT ON COLUMN rag_upsert_history.qdrant_point_id IS 'Qdrant에 저장된 벡터 포인트 ID';
COMMENT ON COLUMN rag_upsert_history.vector_dim IS '임베딩 벡터 차원 수';
COMMENT ON COLUMN rag_upsert_history.status IS '업서트 처리 상태';
COMMENT ON COLUMN rag_upsert_history.error_message IS '실패 시 상세 오류 메시지';
COMMENT ON COLUMN rag_upsert_history.created_at IS '레코드 생성 시각(자동 기록)';

-- ============================================================
-- 15. rag_processing_stats (문서별 임베딩 처리 통계)
-- 설명: 문서 버전 단위로 임베딩 처리 결과 요약 통계를 저장
-- ============================================================

CREATE TABLE rag_processing_stats (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_content_id  UUID NOT NULL REFERENCES doc_document_content(id) ON DELETE CASCADE,
    model_name      VARCHAR(100) NOT NULL,
    model_version   VARCHAR(50) NOT NULL,
    vector_dim      INTEGER NOT NULL,
    total_chunks    INTEGER NOT NULL,
    success_chunks  INTEGER NOT NULL,
    failed_chunks   INTEGER NOT NULL,
    total_tokens    BIGINT NOT NULL DEFAULT 0,
    embed_ms        BIGINT NOT NULL DEFAULT 0,
    content_type    VARCHAR(255) NOT NULL DEFAULT 'application/octet-stream',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE rag_processing_stats IS '문서 버전 단위로 임베딩 처리 결과 요약 통계를 저장';
COMMENT ON COLUMN rag_processing_stats.id IS '처리 통계 레코드 PK(자동생성)';
COMMENT ON COLUMN rag_processing_stats.doc_content_id IS '통계가 속한 문서 버전';
COMMENT ON COLUMN rag_processing_stats.model_name IS '사용된 임베딩 모델 이름';
COMMENT ON COLUMN rag_processing_stats.model_version IS '모델의 버전 문자열';
COMMENT ON COLUMN rag_processing_stats.vector_dim IS '생성된 벡터의 차원';
COMMENT ON COLUMN rag_processing_stats.total_chunks IS '문서에 생성된 총 청크 개수';
COMMENT ON COLUMN rag_processing_stats.success_chunks IS '임베딩 성공 청크 개수';
COMMENT ON COLUMN rag_processing_stats.failed_chunks IS '임베딩 실패 청크 개수';
COMMENT ON COLUMN rag_processing_stats.total_tokens IS '문서 전체 토큰 수';
COMMENT ON COLUMN rag_processing_stats.embed_ms IS '전체 임베딩 처리 소요 시간(ms)';
COMMENT ON COLUMN rag_processing_stats.content_type IS 'MinIO Object의 MIME Type';
COMMENT ON COLUMN rag_processing_stats.created_at IS '통계 생성 시각';

-- ============================================================
-- 15-1. rag_similarity_checks (유사도 검사 결과)
-- 설명: 문서 중복 탐지를 위한 유사도 검사 결과
-- ============================================================

CREATE TABLE rag_similarity_checks (
    id                      BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    doc_content_id          UUID NOT NULL,
    job_id                  UUID,
    sample_count            INTEGER NOT NULL,
    high_similarity_matches INTEGER NOT NULL DEFAULT 0,
    similarity_threshold    DOUBLE PRECISION NOT NULL,
    match_ratio             DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    details                 JSONB,
    memo                    TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    avg_similarity          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    similar_documents       JSONB
);

COMMENT ON TABLE rag_similarity_checks IS 'Similarity check results for duplicate detection';

-- ============================================================
-- 16. storage_object_files (MinIO 오브젝트 메타)
-- 설명: MinIO에 저장된 파일들에 대한 메타데이터를 RDB에서 관리하는 테이블
-- ============================================================

CREATE TABLE storage_object_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_content_id  UUID NOT NULL REFERENCES doc_document_content(id) ON DELETE CASCADE,
    kind            object_kind NOT NULL,
    bucket          VARCHAR(63) NOT NULL,
    object_key      TEXT NOT NULL,
    etag            VARCHAR(64),
    sha256          CHAR(64),
    size_bytes      BIGINT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID REFERENCES auth_users(id),
    content_type    VARCHAR(255)
);

COMMENT ON TABLE storage_object_files IS 'MinIO에 저장된 파일들에 대한 메타데이터를 RDB에서 관리하는 테이블';
COMMENT ON COLUMN storage_object_files.id IS '시스템 자동 생성 PK';
COMMENT ON COLUMN storage_object_files.doc_content_id IS '파일이 속한 문서 버전';
COMMENT ON COLUMN storage_object_files.kind IS 'raw/chunks/embeddings 등 파일 역할';
COMMENT ON COLUMN storage_object_files.bucket IS 'MinIO 버킷명';
COMMENT ON COLUMN storage_object_files.object_key IS 'MinIO 내부 오브젝트 키 경로';
COMMENT ON COLUMN storage_object_files.etag IS 'MinIO ETag 값';
COMMENT ON COLUMN storage_object_files.sha256 IS '파일 SHA-256 해시';
COMMENT ON COLUMN storage_object_files.size_bytes IS '파일 크기(byte)';
COMMENT ON COLUMN storage_object_files.metadata IS '청크 개수, 토큰 수 등 파일 관련 부가 정보';
COMMENT ON COLUMN storage_object_files.created_at IS '메타데이터 생성 시각';
COMMENT ON COLUMN storage_object_files.created_by IS '해당 객체 레코드를 생성한 사용자 ID';
COMMENT ON COLUMN storage_object_files.content_type IS 'MinIO Object의 MIME Type';

-- ============================================================
-- 17. auth_users_alarm (유저 알람)
-- 설명: 유저가 전달 받을 상태 이벤트 알람 테이블
-- ============================================================

CREATE TABLE auth_users_alarm (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    users_id        UUID NOT NULL REFERENCES auth_users(id),
    document_id     UUID REFERENCES doc_documents(id) ON DELETE CASCADE,
    post_id         UUID REFERENCES board_posts(id) ON DELETE CASCADE,
    message         VARCHAR(255),
    is_read         VARCHAR(10) NOT NULL DEFAULT 'N',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE auth_users_alarm IS '유저가 전달 받을 상태 이벤트 알람 테이블';
COMMENT ON COLUMN auth_users_alarm.id IS '알람 ID(UUID)';
COMMENT ON COLUMN auth_users_alarm.users_id IS '유저 ID 외래키';
COMMENT ON COLUMN auth_users_alarm.document_id IS '문서 ID 외래키 (nullable)';
COMMENT ON COLUMN auth_users_alarm.post_id IS '게시글 ID 외래키 (nullable)';
COMMENT ON COLUMN auth_users_alarm.message IS '알람 메시지';
COMMENT ON COLUMN auth_users_alarm.is_read IS 'Y는 읽음, N은 읽지 않음';
COMMENT ON COLUMN auth_users_alarm.created_at IS '알람 생성 시각';

-- ============================================================
-- 17-1. auth_users_login_history (사용자 로그인 이력)
-- 설명: 사용자의 일별 로그인 기록 (하루 1행, 중복 방지)
-- ============================================================

CREATE TABLE auth_users_login_history (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth_users(id),
    unique_login_date   DATE NOT NULL,
    logged_in_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_login_history_user_date UNIQUE (user_id, unique_login_date)
);

CREATE INDEX idx_login_history_user_id ON auth_users_login_history(user_id);
CREATE INDEX idx_login_history_date ON auth_users_login_history(unique_login_date);

COMMENT ON TABLE auth_users_login_history IS '사용자 일별 로그인 이력';
COMMENT ON COLUMN auth_users_login_history.id IS '로그인 이력 ID(UUID)';
COMMENT ON COLUMN auth_users_login_history.user_id IS '유저 ID 외래키';
COMMENT ON COLUMN auth_users_login_history.unique_login_date IS '로그인 날짜 (하루 1행 중복 방지 키)';
COMMENT ON COLUMN auth_users_login_history.logged_in_at IS '해당 날짜 최초 로그인 시각';

-- ============================================================
-- 18. chat_session (채팅 세션)
-- 설명: 유저가 생성한 채팅 1개 세션 단위
-- ============================================================

CREATE TABLE chat_session (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           VARCHAR(255),
    favorites       VARCHAR(10) NOT NULL DEFAULT 'N',
    users_id        UUID NOT NULL REFERENCES auth_users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE chat_session IS '유저가 생성한 채팅 1개 세션 단위';
COMMENT ON COLUMN chat_session.id IS '채팅 세션 ID(UUID)';
COMMENT ON COLUMN chat_session.title IS '채팅방 제목 (첫 질문 기반 자동 생성, 최대 20자)';
COMMENT ON COLUMN chat_session.favorites IS 'Y: 등록, N: 미등록';
COMMENT ON COLUMN chat_session.users_id IS '유저 ID 외래키';
COMMENT ON COLUMN chat_session.created_at IS '채팅 세션 생성 시각';
COMMENT ON COLUMN chat_session.deleted_at IS '소프트 삭제 시각 (NULL이면 정상, 값 있으면 삭제됨)';

-- ============================================================
-- 19. chat_interaction (채팅 내역)
-- 설명: 1개 세션 단위 유저의 채팅 내역 (질문/답변)
-- ============================================================

CREATE TABLE chat_interaction (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type                    VARCHAR(10) NOT NULL DEFAULT 'Q',
    content                 TEXT NOT NULL,
    chat_turn               INTEGER NOT NULL DEFAULT 1,
    feedback                VARCHAR(10) NULL DEFAULT NULL,
    input_tokens            INTEGER NULL,
    output_tokens           INTEGER NULL,
    self_citation_count     INTEGER NOT NULL DEFAULT 0,
    other_citation_count    INTEGER NOT NULL DEFAULT 0,
    session_id              UUID NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE chat_interaction IS '1개 세션 단위 유저의 채팅 내역 (질문/답변)';
COMMENT ON COLUMN chat_interaction.id IS '채팅 내역 ID(UUID)';
COMMENT ON COLUMN chat_interaction.type IS 'Q: 질문, A: 답변';
COMMENT ON COLUMN chat_interaction.content IS '메시지 내용';
COMMENT ON COLUMN chat_interaction.chat_turn IS '해당 채팅 세션 안에서의 메시지 순서';
COMMENT ON COLUMN chat_interaction.feedback IS 'Y: 좋아요, N: 싫어요, NULL: 미제출 (기본값 NULL)';
COMMENT ON COLUMN chat_interaction.input_tokens IS 'LLM 입력 토큰 수 (agent usage.input_tokens). 점수 미반영, 표시용';
COMMENT ON COLUMN chat_interaction.output_tokens IS 'LLM 출력 토큰 수 (agent usage.output_tokens). 점수 미반영, 표시용';
COMMENT ON COLUMN chat_interaction.self_citation_count IS '답변에 인용된 본인 업로드 문서 수 (점수 미반영, 표시용)';
COMMENT ON COLUMN chat_interaction.other_citation_count IS '답변에 인용된 타인 업로드 문서 수 (Heritage +5점/건, 월 50 cap)';
COMMENT ON COLUMN chat_interaction.session_id IS '채팅 세션 ID 외래키';
COMMENT ON COLUMN chat_interaction.created_at IS '채팅 내역 생성 시각';

-- ============================================================
-- 20. chat_document_reference (답변 참조 문서)
-- 설명: 해당 답변에 어떤 문서들이 참조 되었는지 기록
-- ============================================================

CREATE TABLE chat_document_reference (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_content_id  UUID NOT NULL REFERENCES doc_document_content(id) ON DELETE CASCADE,
    chat_interaction_id  UUID NOT NULL REFERENCES chat_interaction(id) ON DELETE CASCADE,
    relevance            DOUBLE PRECISION,
    location             VARCHAR(255),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE chat_document_reference IS '해당 답변에 어떤 문서(버전)들이 참조 되었는지 기록';
COMMENT ON COLUMN chat_document_reference.id IS '답변 참조 문서 ID(UUID)';
COMMENT ON COLUMN chat_document_reference.document_content_id IS '문서 버전 ID 외래키 (doc_document_content)';
COMMENT ON COLUMN chat_document_reference.chat_interaction_id IS '채팅내역 ID 외래키';
COMMENT ON COLUMN chat_document_reference.relevance IS 'RAG 검색 시 Qdrant에서 반환된 유사도 점수 (0.0~1.0, 코사인 유사도)';
COMMENT ON COLUMN chat_document_reference.location IS '참조 문서 내 위치 정보 (페이지 번호 등)';
COMMENT ON COLUMN chat_document_reference.created_at IS '답변 참조 문서 테이블 생성 시각';

-- ============================================================
-- 21. board_types (게시판 종류)
-- 설명: 게시판 종류를 정의하는 테이블 (feedback, notice 등)
-- ============================================================

CREATE TABLE board_types (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            board_type_name NOT NULL UNIQUE,
    description     VARCHAR(200),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE board_types IS '게시판 종류를 정의하는 테이블';
COMMENT ON COLUMN board_types.id IS '게시판 종류 고유 ID(UUID)';
COMMENT ON COLUMN board_types.name IS '게시판 종류 (feedback/notice/suggestion/answer_suggestion)';
COMMENT ON COLUMN board_types.description IS '게시판 설명';
COMMENT ON COLUMN board_types.created_at IS '생성 시각';

-- 기본 게시판 종류 삽입
INSERT INTO board_types (id, name, description) VALUES
    ('d11f4479-e011-44d0-bc16-e3a602312fd5', 'feedback', '사내 테스트 피드백 게시판'),
    ('d11f4479-e011-44d0-bc16-e3a602312fd6', 'suggestion', '서비스 제안 게시판'),
    ('d11f4479-e011-44d0-bc16-e3a602312fd7', 'answer_suggestion', '정답 데이터 제공 게시판');

-- ============================================================
-- 22. board_posts (게시글)
-- 설명: 게시판 게시글을 관리하는 테이블
-- ============================================================

CREATE TABLE board_posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    board_type_id   UUID NOT NULL REFERENCES board_types(id),
    user_id         UUID NOT NULL,
    title           VARCHAR(200) NOT NULL,
    content         TEXT NOT NULL,
    has_image       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE board_posts IS '게시판 게시글을 관리하는 테이블';
COMMENT ON COLUMN board_posts.id IS '게시글 고유 ID(UUID)';
COMMENT ON COLUMN board_posts.board_type_id IS '게시판 종류 ID';
COMMENT ON COLUMN board_posts.user_id IS '작성자 ID (FK 없음 — 퇴사자 데이터 보존)';
COMMENT ON COLUMN board_posts.title IS '게시글 제목';
COMMENT ON COLUMN board_posts.content IS '게시글 본문';
COMMENT ON COLUMN board_posts.has_image IS '이미지 첨부 여부';
COMMENT ON COLUMN board_posts.created_at IS '작성 시각';

-- ============================================================
-- 23. board_post_images (게시글 이미지)
-- 설명: 게시글에 첨부된 이미지를 관리하는 테이블
-- ============================================================

CREATE TABLE board_post_images (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id             UUID NOT NULL REFERENCES board_posts(id) ON DELETE CASCADE,
    object_key          VARCHAR(500) NOT NULL,
    original_filename   VARCHAR(300) NOT NULL,
    file_size           BIGINT,
    mime_type           VARCHAR(100),
    sort_order          SMALLINT NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE board_post_images IS '게시글에 첨부된 이미지를 관리하는 테이블';
COMMENT ON COLUMN board_post_images.id IS '이미지 고유 ID(UUID)';
COMMENT ON COLUMN board_post_images.post_id IS '게시글 ID';
COMMENT ON COLUMN board_post_images.object_key IS 'MinIO 오브젝트 경로';
COMMENT ON COLUMN board_post_images.original_filename IS '원본 파일명';
COMMENT ON COLUMN board_post_images.file_size IS '파일 크기(바이트)';
COMMENT ON COLUMN board_post_images.mime_type IS 'MIME 타입 (image/png 등)';
COMMENT ON COLUMN board_post_images.sort_order IS '정렬 순서';
COMMENT ON COLUMN board_post_images.created_at IS '생성 시각';

-- ============================================================
-- 24. board_comments (댓글)
-- 설명: 게시글 댓글 테이블 (현재 ADMIN 답변용)
-- ============================================================

CREATE TABLE board_comments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id         UUID NOT NULL REFERENCES board_posts(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL,
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

COMMENT ON TABLE board_comments IS '게시글 댓글 테이블 (현재 ADMIN 답변용)';
COMMENT ON COLUMN board_comments.id IS '댓글 고유 ID(UUID)';
COMMENT ON COLUMN board_comments.post_id IS '게시글 ID';
COMMENT ON COLUMN board_comments.user_id IS '작성자 ID (FK 없음 — 퇴사자 데이터 보존)';
COMMENT ON COLUMN board_comments.content IS '댓글 내용';
COMMENT ON COLUMN board_comments.created_at IS '작성 시각';
COMMENT ON COLUMN board_comments.updated_at IS '수정 시각';
COMMENT ON COLUMN board_comments.deleted_at IS 'soft delete 시각';

-- ============================================================
-- 24-1. board_post_adoptions (게시글 채택 결과)
-- 설명: suggestion 게시판의 채택 결과 저장
--       평가위원회 심사 후 ADMIN이 grade(50~200) 입력 → EXpert 점수 합산
--       post_id UNIQUE (게시글당 채택 1회), 월 4건 cap 은 View 계산에서 적용
-- ============================================================

CREATE TABLE board_post_adoptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id         UUID NOT NULL UNIQUE REFERENCES board_posts(id) ON DELETE CASCADE,
    grade           INTEGER NOT NULL CHECK (grade BETWEEN 50 AND 200),
    reviewer_id     UUID NOT NULL REFERENCES auth_users(id),
    reviewed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_board_post_adoptions_post_id ON board_post_adoptions(post_id);
CREATE INDEX idx_board_post_adoptions_reviewed_at ON board_post_adoptions(reviewed_at);

COMMENT ON TABLE board_post_adoptions IS 'suggestion 게시글의 평가위원회 채택 결과';
COMMENT ON COLUMN board_post_adoptions.id IS '채택 ID(UUID)';
COMMENT ON COLUMN board_post_adoptions.post_id IS '대상 게시글 ID (UNIQUE)';
COMMENT ON COLUMN board_post_adoptions.grade IS '채택 등급 (50~200), EXpert 점수에 합산';
COMMENT ON COLUMN board_post_adoptions.reviewer_id IS '채택한 ADMIN ID';
COMMENT ON COLUMN board_post_adoptions.reviewed_at IS '채택 시각 (월 4건 cap 기준)';
COMMENT ON COLUMN board_post_adoptions.created_at IS '생성 시각';

-- ============================================================
-- 25. board_surveys (사용성 설문 응답)
-- 설명: 사용성 테스트 설문 응답을 저장하는 테이블
-- 점수 컬럼: SMALLINT (1~5), CHECK 제약 적용
-- ============================================================

CREATE TABLE board_surveys (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL,

    -- 로그인/회원가입 경험
    login_understand        SMALLINT NOT NULL CHECK (login_understand BETWEEN 1 AND 5),
    login_simple            SMALLINT NOT NULL CHECK (login_simple BETWEEN 1 AND 5),

    -- 홈 화면 경험
    home_intuitive          SMALLINT NOT NULL CHECK (home_intuitive BETWEEN 1 AND 5),
    home_input_position     SMALLINT NOT NULL CHECK (home_input_position BETWEEN 1 AND 5),
    home_natural_start      SMALLINT NOT NULL CHECK (home_natural_start BETWEEN 1 AND 5),

    -- 채팅 및 AI 답변 품질
    chat_speed              SMALLINT NOT NULL CHECK (chat_speed BETWEEN 1 AND 5),
    chat_easy               SMALLINT NOT NULL CHECK (chat_easy BETWEEN 1 AND 5),
    chat_length             SMALLINT NOT NULL CHECK (chat_length BETWEEN 1 AND 5),
    chat_process_helpful    SMALLINT NOT NULL CHECK (chat_process_helpful BETWEEN 1 AND 5),

    -- 출처 보기 기능
    source_visible          SMALLINT NOT NULL CHECK (source_visible BETWEEN 1 AND 5),
    source_ui_easy          SMALLINT NOT NULL CHECK (source_ui_easy BETWEEN 1 AND 5),
    source_trust            SMALLINT NOT NULL CHECK (source_trust BETWEEN 1 AND 5),

    -- 문서함 기능
    doc_upload_easy         SMALLINT NOT NULL CHECK (doc_upload_easy BETWEEN 1 AND 5),
    doc_status_clear        SMALLINT NOT NULL CHECK (doc_status_clear BETWEEN 1 AND 5),
    doc_ai_knowledge        SMALLINT NOT NULL CHECK (doc_ai_knowledge BETWEEN 1 AND 5),

    -- 업무 활용도
    work_helpful            SMALLINT NOT NULL CHECK (work_helpful BETWEEN 1 AND 5),
    work_better_than_llm    SMALLINT NOT NULL CHECK (work_better_than_llm BETWEEN 1 AND 5),

    -- 주관식
    best_feature            TEXT NOT NULL,
    worst_feature           TEXT NOT NULL,
    free_comment            TEXT,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE board_surveys IS '사용성 테스트 설문 응답 (1인 1회, user_id UNIQUE)';
COMMENT ON COLUMN board_surveys.id IS '설문 응답 고유 ID(UUID)';
COMMENT ON COLUMN board_surveys.user_id IS '응답자 ID (FK 없음 — 퇴사자 데이터 보존)';
COMMENT ON COLUMN board_surveys.login_understand IS '로그인 화면에서 서비스가 무엇인지 이해할 수 있었는가 (1~5)';
COMMENT ON COLUMN board_surveys.login_simple IS '회원가입/로그인 과정은 빠르고 간결했는가 (1~5)';
COMMENT ON COLUMN board_surveys.home_intuitive IS '첫 화면에서 무엇을 해야 하는지 바로 이해 가능했는가 (1~5)';
COMMENT ON COLUMN board_surveys.home_input_position IS '질문 입력창 위치와 크기는 적절했는가 (1~5)';
COMMENT ON COLUMN board_surveys.home_natural_start IS 'AI에게 질문을 시작하는 과정이 자연스러웠는가 (1~5)';
COMMENT ON COLUMN board_surveys.chat_speed IS 'AI 답변 생성 속도는 적절했는가 (1~5)';
COMMENT ON COLUMN board_surveys.chat_easy IS 'AI 답변은 이해하기 쉬웠는가 (1~5)';
COMMENT ON COLUMN board_surveys.chat_length IS '답변 길이는 적절했는가 (1~5)';
COMMENT ON COLUMN board_surveys.chat_process_helpful IS 'AI가 답변 생성 과정을 보여주는 기능은 도움이 되었는가 (1~5)';
COMMENT ON COLUMN board_surveys.source_visible IS 'AI 답변에 출처가 제공된다는 것을 쉽게 인지할 수 있었는가 (1~5)';
COMMENT ON COLUMN board_surveys.source_ui_easy IS '출처 패널 UI는 이해하기 쉬웠는가 (1~5)';
COMMENT ON COLUMN board_surveys.source_trust IS '출처 정보는 AI 답변을 신뢰하는 데 도움이 되었는가 (1~5)';
COMMENT ON COLUMN board_surveys.doc_upload_easy IS '문서 업로드 과정은 이해하기 쉬웠는가 (1~5)';
COMMENT ON COLUMN board_surveys.doc_status_clear IS '문서 상태를 이해하기 쉬웠는가 (1~5)';
COMMENT ON COLUMN board_surveys.doc_ai_knowledge IS 'AI 지식 추가 기능의 목적을 이해할 수 있었는가 (1~5)';
COMMENT ON COLUMN board_surveys.work_helpful IS '이 AI 서비스는 실제 업무에 도움이 될 것 같은가 (1~5)';
COMMENT ON COLUMN board_surveys.work_better_than_llm IS '기존 AI LLM 서비스보다 업무 효율이 높아질 것 같은가 (1~5)';
COMMENT ON COLUMN board_surveys.best_feature IS '가장 좋았던 기능 (주관식)';
COMMENT ON COLUMN board_surveys.worst_feature IS '가장 불편했던 점 (주관식)';
COMMENT ON COLUMN board_surveys.free_comment IS '기타 자유 의견 (선택)';
COMMENT ON COLUMN board_surveys.created_at IS '제출 시각';

-- ============================================================
-- 인덱스 생성
-- ============================================================

-- auth_users
CREATE INDEX idx_auth_users_email ON auth_users(email);
CREATE INDEX idx_auth_users_dept_id ON auth_users(auth_dept_id);

-- auth_users_authority_permission
CREATE INDEX idx_auth_users_authority_permission_authority_id ON auth_users_authority_permission(authority_id);
CREATE INDEX idx_auth_users_authority_permission_users_id ON auth_users_authority_permission(users_id);

-- auth_users_dept_authority_permission
CREATE INDEX idx_auth_users_dept_authority_permission_users_id ON auth_users_dept_authority_permission(users_id);
CREATE INDEX idx_auth_users_dept_authority_permission_dept_id ON auth_users_dept_authority_permission(dept_id);

-- auth_users_alarm
CREATE INDEX idx_auth_users_alarm_users_id ON auth_users_alarm(users_id);
CREATE INDEX idx_auth_users_alarm_is_read ON auth_users_alarm(is_read);

-- doc_documents
CREATE INDEX idx_doc_documents_created_by ON doc_documents(created_by);
CREATE INDEX idx_doc_documents_created_at ON doc_documents(created_at);

-- doc_document_content
CREATE INDEX idx_doc_document_content_document_id ON doc_document_content(document_id);
CREATE INDEX idx_doc_document_content_uploader_id ON doc_document_content(uploader_id);
CREATE INDEX idx_doc_document_content_status ON doc_document_content(status);
CREATE INDEX idx_doc_document_content_deleted_at ON doc_document_content(deleted_at);

-- doc_document_favorites
CREATE INDEX idx_doc_document_favorites_document_id ON doc_document_favorites(document_id);
CREATE INDEX idx_doc_document_favorites_users_id ON doc_document_favorites(users_id);

-- doc_user_tags
CREATE INDEX idx_doc_user_tags_user_id ON doc_user_tags(user_id);

-- doc_user_tag_mappings
CREATE INDEX idx_doc_user_tag_mappings_user_id ON doc_user_tag_mappings(user_id);
CREATE INDEX idx_doc_user_tag_mappings_document_id ON doc_user_tag_mappings(document_id);
CREATE INDEX idx_doc_user_tag_mappings_tag_id ON doc_user_tag_mappings(tag_id);
CREATE INDEX idx_doc_user_tag_mappings_user_document ON doc_user_tag_mappings(user_id, document_id);

-- doc_document_exclude
CREATE INDEX idx_doc_document_exclude_user_id ON doc_document_exclude(user_id);
CREATE INDEX idx_doc_document_exclude_content_id ON doc_document_exclude(document_content_id);

-- doc_embed_review
CREATE INDEX idx_doc_embed_review_doc_content_id ON doc_embed_review(doc_content_id);
CREATE INDEX idx_doc_embed_review_reviewer_id ON doc_embed_review(reviewer_id);

-- rag_embedding_jobs
CREATE INDEX idx_rag_embedding_jobs_doc_content_id ON rag_embedding_jobs(doc_content_id);
CREATE INDEX idx_rag_embedding_jobs_status ON rag_embedding_jobs(status);
CREATE INDEX idx_rag_embedding_jobs_enqueued_at ON rag_embedding_jobs(enqueued_at);

-- rag_status_events
CREATE INDEX idx_rag_status_events_doc_content_id ON rag_status_events(doc_content_id);
CREATE INDEX idx_rag_status_events_job_id ON rag_status_events(job_id);
CREATE INDEX idx_rag_status_events_created_at ON rag_status_events(created_at);

-- rag_chunks
CREATE INDEX idx_rag_chunks_doc_content_id ON rag_chunks(doc_content_id);
CREATE INDEX idx_rag_chunks_text_hash ON rag_chunks(text_hash);
CREATE INDEX idx_chunks_extraction_version ON rag_chunks(extraction_version);

-- rag_embeddings_index
CREATE INDEX idx_rag_embeddings_index_doc_content_id ON rag_embeddings_index(doc_content_id);
CREATE INDEX idx_rag_embeddings_index_chunk_id ON rag_embeddings_index(chunk_id);
CREATE INDEX idx_rag_embeddings_index_qdrant_collection ON rag_embeddings_index(qdrant_collection_name);
CREATE INDEX idx_embeddings_index_ver ON rag_embeddings_index(embedding_version);

-- rag_upsert_history
CREATE INDEX idx_rag_upsert_history_doc_content_id ON rag_upsert_history(doc_content_id);
CREATE INDEX idx_rag_upsert_history_chunk_id ON rag_upsert_history(chunk_id);
CREATE INDEX idx_rag_upsert_history_job_id ON rag_upsert_history(job_id);

-- rag_processing_stats
CREATE INDEX idx_rag_processing_stats_doc_content_id ON rag_processing_stats(doc_content_id);

-- rag_similarity_checks
CREATE INDEX idx_rag_similarity_checks_doc_content_id ON rag_similarity_checks(doc_content_id);
CREATE INDEX idx_rag_similarity_checks_job_id ON rag_similarity_checks(job_id);

-- storage_object_files
CREATE INDEX idx_storage_object_files_doc_content_id ON storage_object_files(doc_content_id);
CREATE INDEX idx_storage_object_files_kind ON storage_object_files(kind);
CREATE INDEX idx_storage_object_files_bucket ON storage_object_files(bucket);

-- chat_session
CREATE INDEX idx_chat_session_users_id ON chat_session(users_id);

-- chat_interaction
CREATE INDEX idx_chat_interaction_session_id ON chat_interaction(session_id);
CREATE INDEX idx_chat_interaction_type ON chat_interaction(type);

-- chat_document_reference
CREATE INDEX idx_chat_document_reference_doc_content_id ON chat_document_reference(document_content_id);
CREATE INDEX idx_chat_document_reference_chat_interaction_id ON chat_document_reference(chat_interaction_id);

-- board_posts
CREATE INDEX idx_board_posts_board_type_id ON board_posts(board_type_id);
CREATE INDEX idx_board_posts_user_id ON board_posts(user_id);
CREATE INDEX idx_board_posts_created_at ON board_posts(created_at);

-- board_post_images
CREATE INDEX idx_board_post_images_post_id ON board_post_images(post_id);

-- board_comments
CREATE INDEX idx_board_comments_post_id ON board_comments(post_id);
CREATE INDEX idx_board_comments_user_id ON board_comments(user_id);

-- board_surveys
CREATE INDEX idx_board_surveys_user_id ON board_surveys(user_id);

-- ============================================================
-- Materialized View: user_activity_summary
-- Story 3.8: 사용자 활동 모니터링 (Persona / Heritage / EXpert)
-- 30분 cron + 수동 갱신 + 일배치(자정), CONCURRENTLY REFRESH 지원
--
-- ▸ 기본점수 1,000은 가중치 적용 대상 아님 (고정)
-- ▸ 활동 점수만 시기/부서 가중치 적용
--
-- ▸ Persona_activity = -3×missed + 5×three + 10×five + 50×√Q
-- ▸ Heritage_upload  = 3 × Σ(월별 업로드, 월 30 cap)
-- ▸ Heritage_cite    = 5 × Σ(월별 타인 인용, 월 50 cap)
-- ▸ EXpert_activity  = 5 × feedback + 20 × answer_sug + Σ(adoption.grade, 월 4건 cap)
--
-- ▸ 시기별 가중치 (현재 월 기준)
--   - 도입기(2026-06~08): Persona_activity × 1.2, Heritage_upload × 1.2
--   - 확산기(2026-09~12): Heritage_cite × 1.5, EXpert_activity × 1.5
--   - 그 외: ×1.0
--
-- ▸ 1차 활동 합 = (가중치 적용된 P_activity + H_up + H_cite + EX)
-- ▸ 1차 total = 1000 + 1차 활동 합
-- ▸ 1차 eligible = 1차 total ≥ 1200
-- ▸ 부서 배율 = 부서원 중 1차 eligible 비율
--   - <50% → ×0.8 / 50~80% → ×1.0 / ≥80% → ×1.2
--
-- ▸ 최종 total = LEAST(5000, GREATEST(0, 1000 + (1차 활동 합 × 부서 배율)))
-- ▸ Eligible = 최종 total ≥ 1200
-- ============================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS user_activity_summary AS
WITH
-- 1) 시작일 이후 로그인 일수
login_days AS (
  SELECT user_id, COUNT(DISTINCT unique_login_date) AS days
  FROM auth_users_login_history
  WHERE unique_login_date >= DATE '2026-06-04'
  GROUP BY user_id
),
-- 2) 주간 연속 접속 streak (월~일, 매주 리셋)
login_groups AS (
  SELECT
    user_id,
    unique_login_date,
    DATE_TRUNC('week', unique_login_date) AS week_start,
    unique_login_date - (
      ROW_NUMBER() OVER (
        PARTITION BY user_id, DATE_TRUNC('week', unique_login_date)
        ORDER BY unique_login_date
      )
    )::int AS grp
  FROM auth_users_login_history
  WHERE unique_login_date >= DATE '2026-06-04'
),
login_streaks AS (
  SELECT user_id, week_start, grp,
         ROW_NUMBER() OVER (
           PARTITION BY user_id, week_start, grp
           ORDER BY unique_login_date
         ) AS streak_day
  FROM login_groups
),
streak_bonus AS (
  SELECT user_id,
         COUNT(*) FILTER (WHERE streak_day = 3) AS three_day,
         COUNT(*) FILTER (WHERE streak_day = 5) AS five_day
  FROM login_streaks
  GROUP BY user_id
),
-- 3) 질문 수 (Persona √Q × 50)
question_count AS (
  SELECT s.users_id AS user_id, COUNT(*) AS cnt
  FROM chat_interaction i
  JOIN chat_session s ON s.id = i.session_id
  WHERE i.type = 'Q'
  GROUP BY s.users_id
),
-- 4) 월별 업로드 (임베딩 완료 + 미삭제, 월 30 cap)
upload_capped AS (
  SELECT user_id, SUM(monthly) AS total
  FROM (
    SELECT uploader_id AS user_id,
           LEAST(COUNT(*), 30) AS monthly
    FROM doc_document_content
    WHERE status = 'completed' AND deleted_at IS NULL
    GROUP BY uploader_id, DATE_TRUNC('month', created_at)
  ) m
  GROUP BY user_id
),
-- 5) 월별 인용 (타인 문서 월 50 cap, 본인 인용은 표시용)
citation_monthly AS (
  SELECT
    s.users_id AS user_id,
    DATE_TRUNC('month', i.created_at) AS month,
    LEAST(SUM(COALESCE(i.other_citation_count, 0)), 50) AS monthly_other,
    SUM(COALESCE(i.self_citation_count, 0)) AS monthly_self
  FROM chat_interaction i
  JOIN chat_session s ON s.id = i.session_id
  WHERE i.type = 'A'
  GROUP BY s.users_id, DATE_TRUNC('month', i.created_at)
),
citation_total AS (
  SELECT
    user_id,
    SUM(monthly_other)::int AS other_citation_count,
    SUM(monthly_self)::int AS self_citation_count
  FROM citation_monthly
  GROUP BY user_id
),
-- 6) EXpert: feedback / answer_suggestion 게시글 카운트
expert_posts AS (
  SELECT
    p.user_id,
    COUNT(*) FILTER (WHERE t.name = 'feedback')::int AS feedback_count,
    COUNT(*) FILTER (WHERE t.name = 'answer_suggestion')::int AS answer_suggestion_count
  FROM board_posts p
  JOIN board_types t ON t.id = p.board_type_id
  GROUP BY p.user_id
),
-- 7) EXpert: 채택 점수 (월 4건 cap)
adoption_ranked AS (
  SELECT
    p.user_id,
    a.grade,
    ROW_NUMBER() OVER (
      PARTITION BY p.user_id, DATE_TRUNC('month', a.reviewed_at)
      ORDER BY a.reviewed_at
    ) AS rn
  FROM board_post_adoptions a
  JOIN board_posts p ON p.id = a.post_id
),
adoption_capped AS (
  SELECT user_id, SUM(grade)::int AS adoption_score
  FROM adoption_ranked
  WHERE rn <= 4
  GROUP BY user_id
),
-- 8) 마지막 활동
all_activities AS (
  SELECT s.users_id AS user_id, MAX(i.created_at) AS activity_at, 'chat'::text AS activity_type
  FROM chat_interaction i
  JOIN chat_session s ON s.id = i.session_id
  WHERE s.deleted_at IS NULL
  GROUP BY s.users_id
  UNION ALL
  SELECT uploader_id, MAX(created_at), 'upload'
  FROM doc_document_content WHERE deleted_at IS NULL GROUP BY uploader_id
  UNION ALL
  SELECT p.user_id, MAX(p.created_at), 'feedback'
  FROM board_posts p JOIN board_types t ON t.id = p.board_type_id
  WHERE t.name = 'feedback' GROUP BY p.user_id
  UNION ALL
  SELECT user_id, MAX(created_at), 'survey'
  FROM board_surveys GROUP BY user_id
),
last_activity AS (
  SELECT DISTINCT ON (user_id) user_id, activity_at, activity_type
  FROM all_activities
  WHERE activity_at IS NOT NULL
  ORDER BY user_id, activity_at DESC
),
-- 9) 사용자별 활동 카운트 통합
stats AS (
  SELECT
    u.id AS user_id,
    GREATEST(0, (CURRENT_DATE - DATE '2026-06-04' + 1) - COALESCE(ld.days, 0)) AS missed_days,
    COALESCE(sb.three_day, 0)::int AS three_day_count,
    COALESCE(sb.five_day, 0)::int AS five_day_count,
    COALESCE(qc.cnt, 0)::int AS question_count,
    COALESCE(uc.total, 0)::int AS upload_count,
    COALESCE(ct.other_citation_count, 0)::int AS other_citation_count,
    COALESCE(ct.self_citation_count, 0)::int AS self_citation_count,
    COALESCE(ep.feedback_count, 0)::int AS feedback_count,
    COALESCE(ep.answer_suggestion_count, 0)::int AS answer_suggestion_count,
    COALESCE(ac.adoption_score, 0)::int AS adoption_score
  FROM auth_users u
  LEFT JOIN login_days ld ON ld.user_id = u.id
  LEFT JOIN streak_bonus sb ON sb.user_id = u.id
  LEFT JOIN question_count qc ON qc.user_id = u.id
  LEFT JOIN upload_capped uc ON uc.user_id = u.id
  LEFT JOIN citation_total ct ON ct.user_id = u.id
  LEFT JOIN expert_posts ep ON ep.user_id = u.id
  LEFT JOIN adoption_capped ac ON ac.user_id = u.id
),
-- 10) 시기 판정 (현재 월 기준)
period AS (
  SELECT
    CASE
      WHEN to_char(CURRENT_DATE, 'YYYY-MM') BETWEEN '2026-06' AND '2026-08' THEN 'intro'
      WHEN to_char(CURRENT_DATE, 'YYYY-MM') BETWEEN '2026-09' AND '2026-12' THEN 'expansion'
      ELSE 'default'
    END AS name
),
-- 11) 카테고리별 raw 점수 + 시기 가중치 적용
weighted AS (
  SELECT
    s.*,
    -- 활동 점수 (기본점수 1000은 제외)
    (-3 * s.missed_days
      + 5 * s.three_day_count
      + 10 * s.five_day_count
      + (50 * SQRT(s.question_count))::int) AS persona_activity_raw,
    (3 * s.upload_count)::int AS heritage_upload_raw,
    (5 * s.other_citation_count)::int AS heritage_cite_raw,
    (5 * s.feedback_count + 20 * s.answer_suggestion_count + s.adoption_score)::int AS expert_raw,
    p.name AS period_name
  FROM stats s
  CROSS JOIN period p
),
applied AS (
  SELECT
    w.*,
    -- 시기 가중치 적용 (활동 점수에만)
    CASE WHEN w.period_name = 'intro' THEN (w.persona_activity_raw * 1.2)::int ELSE w.persona_activity_raw END AS persona_activity_score,
    CASE WHEN w.period_name = 'intro' THEN (w.heritage_upload_raw * 1.2)::int ELSE w.heritage_upload_raw END AS heritage_upload_score,
    CASE WHEN w.period_name = 'expansion' THEN (w.heritage_cite_raw * 1.5)::int ELSE w.heritage_cite_raw END AS heritage_cite_score,
    CASE WHEN w.period_name = 'expansion' THEN (w.expert_raw * 1.5)::int ELSE w.expert_raw END AS expert_score_w
  FROM weighted w
),
-- 12) 1차 활동 합 + 1차 total (기본점수 포함) + 1차 eligible
prelim AS (
  SELECT
    a.*,
    (a.persona_activity_score + a.heritage_upload_score + a.heritage_cite_score + a.expert_score_w) AS activity_sum,
    (1000 + a.persona_activity_score + a.heritage_upload_score + a.heritage_cite_score + a.expert_score_w) AS prelim_total
  FROM applied a
),
prelim_eligible AS (
  SELECT
    p.user_id,
    u.auth_dept_id,
    p.prelim_total >= 1200 AS is_eligible
  FROM prelim p
  JOIN auth_users u ON u.id = p.user_id
),
-- 13) 부서별 1차 eligible 비율 → 가점 배율
dept_ratio AS (
  SELECT
    auth_dept_id,
    COUNT(*) AS total_users,
    SUM(CASE WHEN is_eligible THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) * 100 AS eligible_ratio
  FROM prelim_eligible
  WHERE auth_dept_id IS NOT NULL
  GROUP BY auth_dept_id
),
dept_multiplier AS (
  SELECT
    auth_dept_id,
    eligible_ratio,
    CASE
      WHEN eligible_ratio < 50 THEN 0.8
      WHEN eligible_ratio < 80 THEN 1.0
      ELSE 1.2
    END::numeric(3, 1) AS multiplier
  FROM dept_ratio
)
SELECT
  u.id AS user_id,
  u.name AS user_name,
  d.dept_name AS department,
  u.job_title,
  p.missed_days,
  p.three_day_count,
  p.five_day_count,
  p.question_count,
  p.upload_count,
  p.other_citation_count,
  p.self_citation_count,
  p.feedback_count,
  p.answer_suggestion_count,
  p.adoption_score,
  p.period_name,
  COALESCE(dm.multiplier, 1.0)::numeric(3, 1) AS dept_multiplier,
  COALESCE(dm.eligible_ratio, 0)::numeric(5, 2) AS dept_eligible_ratio,
  -- 카테고리별 가중치 적용된 점수 (Persona = 1000 + 활동, Heritage/EXpert는 활동만)
  (1000 + p.persona_activity_score)::int AS persona_score,
  (p.heritage_upload_score + p.heritage_cite_score)::int AS heritage_score,
  p.expert_score_w AS expert_score,
  -- 최종 total = 1000 + (활동 합 × 부서 배율), 상하한 적용
  LEAST(5000, GREATEST(0,
    1000 + (p.activity_sum * COALESCE(dm.multiplier, 1.0))::int
  ))::int AS total_score,
  CASE
    WHEN LEAST(5000, GREATEST(0,
      1000 + (p.activity_sum * COALESCE(dm.multiplier, 1.0))::int
    )) >= 1200
    THEN true ELSE false
  END AS eligible,
  la.activity_at AS last_activity_at,
  la.activity_type AS last_activity_type,
  NOW() AS updated_at
FROM auth_users u
LEFT JOIN auth_users_dept d ON d.id = u.auth_dept_id
LEFT JOIN prelim p ON p.user_id = u.id
LEFT JOIN dept_multiplier dm ON dm.auth_dept_id = u.auth_dept_id
LEFT JOIN last_activity la ON la.user_id = u.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_activity_summary_user_id
  ON user_activity_summary (user_id);

CREATE INDEX IF NOT EXISTS idx_user_activity_summary_total_score
  ON user_activity_summary (total_score DESC);

-- ============================================================
-- END OF DDL
-- ============================================================
