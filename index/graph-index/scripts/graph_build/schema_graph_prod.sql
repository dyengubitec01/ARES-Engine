-- ============================================================================
-- 그래프RAG 테이블 생성 (PROD: ragdb / rag 스키마)
-- ----------------------------------------------------------------------------
-- scripts/graph_build/graph_models.py 의 rag_graph_* 7테이블 ORM 정의에서 추출한 DDL.
-- (dev 환경은 동일 DDL을 rag_dev 스키마에서 Base.metadata.create_all 로 생성함)
--
-- 적용:
--   psql "host=localhost port=5432 dbname=ragdb user=raguser" -f schema_graph_prod.sql
--   또는 DBeaver/psql 에서 ragdb 접속 후 이 파일 실행.
--
-- 안전장치: 모두 IF NOT EXISTS (재실행 무해). FK는 그래프 내부끼리만(ON DELETE CASCADE)
--   → 빌드 1건 삭제 시 그 빌드의 엔티티/엣지/청크매핑/커뮤니티 일괄 GC.
--   rag_chunks / doc_document_content 로의 FK는 의도적으로 없음(스토어 분리, plain UUID).
-- 전제: uuid_generate_v4() (uuid-ossp) 가 ragdb 에 이미 설치돼 있어야 함(운영 기존 테이블이 사용 중).
-- ============================================================================

SET search_path TO rag, public;

-- 1) 빌드 버전 (materialized-view 포인터). status: building/active/superseded/failed
CREATE TABLE IF NOT EXISTS rag_graph_builds (
	id BIGSERIAL NOT NULL,
	status VARCHAR(20) DEFAULT 'building' NOT NULL,
	started_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	finished_at TIMESTAMP WITHOUT TIME ZONE,
	corpus_chunk_count INTEGER,
	entity_count INTEGER,
	edge_count INTEGER,
	community_count INTEGER,
	params JSONB,
	note TEXT,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
);

-- 2) 커뮤니티 (Louvain). 빌드 종속.
CREATE TABLE IF NOT EXISTS rag_graph_communities (
	id UUID DEFAULT uuid_generate_v4() NOT NULL,
	build_id BIGINT NOT NULL,
	level INTEGER DEFAULT 0 NOT NULL,
	label TEXT,
	summary TEXT,
	entity_count INTEGER DEFAULT 0 NOT NULL,
	metadata JSONB,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(build_id) REFERENCES rag_graph_builds (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_rag_graph_communities_build_id ON rag_graph_communities (build_id);

-- 3) 엔티티 (정규화명으로 문서간 병합). 빌드 종속.
CREATE TABLE IF NOT EXISTS rag_graph_entities (
	id UUID DEFAULT uuid_generate_v4() NOT NULL,
	build_id BIGINT NOT NULL,
	name TEXT NOT NULL,
	entity_type VARCHAR(64) DEFAULT 'UNKNOWN' NOT NULL,
	normalized_name TEXT NOT NULL,
	qdrant_point_id VARCHAR(128),
	description TEXT,  -- LLM 엔티티 설명(describe_entities). 기존 prod 테이블은 아래 ALTER로 추가(admin)
	community_id UUID,
	chunk_count INTEGER DEFAULT 0 NOT NULL,
	metadata JSONB,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_rag_graph_entity_canon UNIQUE (build_id, normalized_name, entity_type),
	FOREIGN KEY(build_id) REFERENCES rag_graph_builds (id) ON DELETE CASCADE,
	FOREIGN KEY(community_id) REFERENCES rag_graph_communities (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entities_community_id ON rag_graph_entities (community_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entities_normalized_name ON rag_graph_entities (normalized_name);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entities_build_id ON rag_graph_entities (build_id);
-- 이미 존재하는 prod 테이블에 description 컬럼 추가(신규 생성은 위 CREATE에 포함). admin 실행.
ALTER TABLE rag_graph_entities ADD COLUMN IF NOT EXISTS description TEXT;

-- 4) 엔티티-청크 매핑 (chunk_id/doc_content_id 는 FK 없는 plain UUID = 스토어 분리)
CREATE TABLE IF NOT EXISTS rag_graph_entity_chunks (
	id BIGSERIAL NOT NULL,
	build_id BIGINT NOT NULL,
	entity_id UUID NOT NULL,
	chunk_id UUID NOT NULL,
	doc_content_id UUID NOT NULL,
	occurrence_count INTEGER DEFAULT 1 NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(build_id) REFERENCES rag_graph_builds (id) ON DELETE CASCADE,
	FOREIGN KEY(entity_id) REFERENCES rag_graph_entities (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entity_chunks_build_id ON rag_graph_entity_chunks (build_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entity_chunks_doc_content_id ON rag_graph_entity_chunks (doc_content_id);
CREATE INDEX IF NOT EXISTS ix_gec_build_entity ON rag_graph_entity_chunks (build_id, entity_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entity_chunks_chunk_id ON rag_graph_entity_chunks (chunk_id);
-- entity_id 단독 인덱스: 엔티티 삭제 시 cascade(WHERE entity_id=?) 가속. 없으면 풀스캔으로 GC 폭사.
CREATE INDEX IF NOT EXISTS ix_gec_entity ON rag_graph_entity_chunks (entity_id);

-- 5) 엣지 (공출현 강도 weight + LLM 관계 라벨/요약)
CREATE TABLE IF NOT EXISTS rag_graph_edges (
	id BIGSERIAL NOT NULL,
	build_id BIGINT NOT NULL,
	source_entity_id UUID NOT NULL,
	target_entity_id UUID NOT NULL,
	weight FLOAT DEFAULT 1 NOT NULL,
	relation_label TEXT,
	relation_summary TEXT,
	metadata JSONB,
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(build_id) REFERENCES rag_graph_builds (id) ON DELETE CASCADE,
	FOREIGN KEY(source_entity_id) REFERENCES rag_graph_entities (id) ON DELETE CASCADE,
	FOREIGN KEY(target_entity_id) REFERENCES rag_graph_entities (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_rag_graph_edges_build_id ON rag_graph_edges (build_id);
CREATE INDEX IF NOT EXISTS ix_gedge_build_source ON rag_graph_edges (build_id, source_entity_id);
CREATE INDEX IF NOT EXISTS ix_gedge_build_target ON rag_graph_edges (build_id, target_entity_id);
-- source/target 단독 인덱스: 엔티티 삭제 시 cascade(WHERE source/target_entity_id=?) 가속.
-- 없으면 엣지 풀스캔으로 엔티티 GC 폭사(45만 삭제 21분+). GC 필수 인덱스.
CREATE INDEX IF NOT EXISTS ix_gedge_source_entity ON rag_graph_edges (source_entity_id);
CREATE INDEX IF NOT EXISTS ix_gedge_target_entity ON rag_graph_edges (target_entity_id);

-- 6) 요약 캐시 (text_checksum 기반 LLM 재사용 → 비용 델타비례). 빌드 무관(전역).
CREATE TABLE IF NOT EXISTS rag_graph_summary_cache (
	id BIGSERIAL NOT NULL,
	cache_key VARCHAR(128) NOT NULL,
	summary_kind VARCHAR(20) NOT NULL,
	summary_text TEXT NOT NULL,
	model_name VARCHAR(128),
	created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	last_used_at TIMESTAMP WITHOUT TIME ZONE,
	PRIMARY KEY (id),
	UNIQUE (cache_key)
);

-- 7) 문서별 그래프 구축 상태 (RDB에서 어떤 문서가 됐/안됐는지 조회). status: done/no_entities
CREATE TABLE IF NOT EXISTS rag_graph_doc_status (
	id BIGSERIAL NOT NULL,
	build_id BIGINT NOT NULL,
	doc_content_id UUID NOT NULL,
	original_filename TEXT,
	status VARCHAR(20) NOT NULL,
	chunk_count INTEGER DEFAULT 0 NOT NULL,
	entity_count INTEGER DEFAULT 0 NOT NULL,
	processed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_rag_graph_doc_status UNIQUE (build_id, doc_content_id),
	FOREIGN KEY(build_id) REFERENCES rag_graph_builds (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_rag_graph_doc_status_doc_content_id ON rag_graph_doc_status (doc_content_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_doc_status_build_id ON rag_graph_doc_status (build_id);

-- ============================================================================
-- 권한 부여: 컨테이너 접속 계정 raguser 에 DML + 시퀀스 사용권.
-- 이 파일을 raguser 가 아닌 다른 소유자가 실행하면(테이블 소유자≠raguser),
-- raguser 가 INSERT 시 "permission denied for sequence rag_graph_builds_id_seq" 발생.
-- 아래로 raguser 에 테이블 DML + BIGSERIAL 시퀀스 USAGE 부여(재실행 무해).
-- ============================================================================
GRANT USAGE ON SCHEMA rag TO raguser;

GRANT SELECT, INSERT, UPDATE, DELETE ON
    rag_graph_builds, rag_graph_communities, rag_graph_entities,
    rag_graph_entity_chunks, rag_graph_edges, rag_graph_summary_cache, rag_graph_doc_status
    TO raguser;

GRANT USAGE, SELECT ON
    rag_graph_builds_id_seq, rag_graph_entity_chunks_id_seq, rag_graph_edges_id_seq,
    rag_graph_summary_cache_id_seq, rag_graph_doc_status_id_seq
    TO raguser;
